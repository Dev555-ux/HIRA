"""MessagingService — the single messaging orchestration layer (Sprint 64A
PR 7).

Purpose: every inbound message enters through this class; every outbound
message exits through it. Before this PR, that orchestration was split
three ways — inbound persistence/dedup inline in `webhooks/whatsapp.py`,
Autonomous Mode's send in `ai/processing.py::_auto_send`, Assisted Mode's
send in `services/replies.py::approve_and_send` — with the same
"check connection, check window, send, mark terminal" shape duplicated
across the latter two. This module is those three call sites relocated,
not rewritten: every line of persistence/dedup/tool-execution/status-
transition logic is unchanged from where it used to live — see each
method's docstring for exactly which pre-PR-7 function it replaces.

Responsibilities:

Inbound — `record_inbound()`: persist `NormalizedMessage`s (get-or-create
Customer/Conversation, dedupe by external message id, insert Message rows,
update conversation timestamps, enqueue the AI reply job).

Outbound — `send_reply()` (Autonomous Mode) and `approve_and_send()`
(Assisted Mode): persist the final send outcome, run governed tool
execution where one is proposed, call `ChannelManager.send()`, record the
resulting `DeliveryReceipt` onto the `Message` row.

Must never do: parse a channel's native payload (that's Provider's job),
decide retry policy or log per-attempt (that's ChannelManager's job), or
change what the AI decided to say or which CRM/calendar action to take
(unchanged from before this PR — this is a relocation of orchestration,
not a redesign of AI/CRM behavior).

The one layer in this pipeline allowed to touch the database — providers
and ChannelManager are both explicitly DB-free by contract (see their own
module docstrings).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.llm.base import ToolCall
from app.ai.tools import confirmation_message_for, execute_tool_call
from app.calendar.providers.base import CalendarError
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import ChannelError
from app.channels.base.message import MediaKind, MediaRef, NormalizedMessage, OutboundMessage
from app.core.config import settings
from app.instagram.credentials import get_page_access_token as get_instagram_access_token
from app.instagram.credentials import get_stored_credential as get_stored_instagram_credential
from app.jobs import enqueue_job
from app.models import Business, Conversation, Customer, Message
from app.services.channel_manager import ChannelManager
from app.services.execution_traces import get_pending_action
from app.services.messaging import WhatsAppNotConnectedError, WhatsAppSendError
from app.services.replies import get_pending_reply
from app.whatsapp.credentials import get_access_token as get_whatsapp_access_token
from app.whatsapp.credentials import get_stored_credential as get_stored_whatsapp_credential

logger = logging.getLogger(__name__)

# Sprint 65 PR 5: human-readable label for a channel id, used only in
# log lines and user-facing error text (never for behavior — nothing
# branches on the label itself). Falls back to the raw id for a channel
# not yet listed here, rather than raising.
_CHANNEL_LABELS = {"whatsapp": "WhatsApp", "instagram": "Instagram"}


def _channel_label(channel: str) -> str:
    return _CHANNEL_LABELS.get(channel, channel)


# Unchanged from app/webhooks/whatsapp.py's pre-PR-7 SERVICE_WINDOW — every
# inbound message still extends Conversation.window_expires_at by exactly
# 24h, regardless of channel (WhatsApp's own rule; not yet conditioned on
# a channel capability since there is only one channel today — see
# Sprint 65 technical debt notes).
SERVICE_WINDOW = timedelta(hours=24)

# Unchanged from app/ai/processing.py's pre-PR-7 constant.
AUTONOMOUS_TOOL_FAILURE_TEXT = (
    "I wasn't able to complete that automatically, so I've flagged it for the team — "
    "they'll follow up with you shortly."
)


def _serialize_media(media: tuple[MediaRef, ...]) -> list[dict] | None:
    """`Message.media`'s storage shape — a plain list of dicts, the same
    fields `MediaRef` carries. `None` (not `[]`) for no media, matching
    every other optional JSONB column on this model (e.g. `ai_meta`)."""
    if not media:
        return None
    return [
        {"kind": ref.kind.value, "url": ref.url, "mime_type": ref.mime_type, "caption": ref.caption}
        for ref in media
    ]


def _deserialize_media(media: list[dict] | None) -> tuple[MediaRef, ...]:
    """Inverse of `_serialize_media` — reads a `Message.media` column back
    into the `MediaRef` tuple `OutboundMessage.media` expects."""
    if not media:
        return ()
    return tuple(
        MediaRef(
            kind=MediaKind(item["kind"]),
            url=item["url"],
            mime_type=item.get("mime_type"),
            caption=item.get("caption"),
        )
        for item in media
    )


class WhatsAppWindowExpiredError(RuntimeError):
    """The customer's 24-hour WhatsApp service window has closed — a
    free-form text send would violate Meta's platform rules (a template
    message would be required instead, not yet supported). Raised before
    any tool call or send is attempted, same as WhatsAppNotConnectedError,
    so a booking can't execute with no way left to notify the customer it
    happened. Relocated from app/services/replies.py in Sprint 64A PR 7 —
    same class, same meaning, moved alongside approve_and_send()."""


@dataclass(frozen=True)
class _SendContext:
    """What `MessagingService._send()` needs to build an `OutboundMessage`/
    `ChannelCredentials` pair — resolved per-channel by
    `MessagingService._resolve_send_context()` (Sprint 65 PR 5). Not a
    public DTO: this never leaves `MessagingService`, unlike the
    `app.channels.base` DTOs a `ChannelProvider` speaks."""

    channel: str
    external_account_id: str
    external_conversation_id: str
    access_token: str


class MessagingService:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------

    def record_inbound(
        self, business_id: uuid.UUID, messages: Sequence[NormalizedMessage]
    ) -> list[tuple]:
        """Persist inbound messages; return (conversation_id, message_id,
        wa_message_id, text) for new ones — same shape
        `webhooks/whatsapp.py::_persist_inbound` (pre-PR-7) returned, so
        `receive()`'s legacy-dispatch loop needs no change.

        Replaces `_persist_inbound`. Business resolution is no longer done
        here (it was, per-`change`, before PR 5 already simplified it away
        at the webhook level — see that PR's notes) — the caller (the
        webhook route) resolves the single business a signed payload
        belongs to once, before parsing, and passes `business_id` in.

        Commits once per message rather than once per Meta "change" (the
        pre-PR-7 granularity): once messages arrive as a flat, channel-
        agnostic `NormalizedMessage` list (no "which change" grouping
        survives `Provider.parse_webhook()`), per-message commits are the
        natural boundary — strictly finer-grained than before, so nothing
        that committed before now doesn't; the difference is invisible to
        every current test and to Meta's real traffic, which sends one
        message per change in practice anyway.

        When `use_transactional_outbox` is enabled, the AI-reply job is
        enqueued here — inside the same transaction that persists the
        inbound Message and before its commit — so the message and its
        job land atomically, unchanged from before this PR.
        """
        new_inbound: list[tuple] = []
        now = datetime.now(timezone.utc)
        for normalized in messages:
            # Sprint 65 PR 3: these two used to read normalized.raw.get("id")/
            # ("from") — WhatsApp Cloud API's own native JSON key names,
            # not this DTO's channel-agnostic fields. Harmless while
            # WhatsApp was the only channel (its .raw dict happens to use
            # those exact keys, so the values were always identical), but
            # Instagram's native payload has neither key — both reads would
            # silently return None, turning the dedupe check below into
            # "WHERE wa_message_id IS NULL" (matches any other NULL-id row)
            # and the customer lookup into "WHERE wa_phone IS NULL"
            # (collapses every Instagram sender into one existing
            # NULL-phone customer). Reading the DTO's own fields instead is
            # a byte-for-byte no-op for WhatsApp (same source values, see
            # app/channels/whatsapp/parsing.py::parse_messages) and the fix
            # Instagram actually needs.
            wa_message_id = normalized.external_message_id
            already = self._db.scalars(
                select(Message).where(Message.wa_message_id == wa_message_id)
            ).first()
            if already is not None:
                continue  # dedupe

            wa_phone = normalized.external_conversation_id
            customer = self._get_or_create_customer(
                business_id, wa_phone, normalized.sender_display_name
            )
            conversation = self._get_or_create_conversation(
                business_id, customer.id, now, normalized.channel
            )

            body = normalized.text
            # Sprint 65 PR 6: `normalized.media` (channel-agnostic, populated
            # by any provider that implements attachment parsing) takes
            # priority over `raw.get("type")` (a WhatsApp-specific hack —
            # WhatsApp's own `.raw` message dict happens to carry Meta's
            # native "type" field; Instagram's does not, which is exactly
            # why Instagram media messages need this derivation instead).
            message_type = (
                normalized.media[0].kind.value
                if normalized.media
                else normalized.raw.get("type", "text")
            )
            message = Message(
                conversation_id=conversation.id,
                business_id=business_id,
                direction="inbound",
                wa_message_id=wa_message_id,
                body=body,
                type=message_type,
                media=_serialize_media(normalized.media),
                status="received",
            )
            self._db.add(message)
            self._db.flush()
            conversation.last_message_at = now
            conversation.window_expires_at = now + SERVICE_WINDOW

            if settings.use_transactional_outbox:
                # Local import: app.ai.tasks imports app.ai.processing at
                # module level, and app.ai.processing needs MessagingService
                # (this class) — a module-level import here would cycle.
                from app.ai.tasks import GENERATE_AI_REPLY_TASK

                enqueue_job(
                    self._db,
                    business_id=business_id,
                    task_name=GENERATE_AI_REPLY_TASK,
                    payload={
                        "conversation_id": str(conversation.id),
                        "message_id": str(message.id),
                        "user_text": body,
                    },
                    idempotency_key=f"{normalized.channel}:{wa_message_id}",
                )

            new_inbound.append((conversation.id, message.id, wa_message_id, body))
            self._db.commit()
        return new_inbound

    def _get_or_create_customer(
        self, business_id: uuid.UUID, wa_phone: str, display_name: str | None
    ) -> Customer:
        """Unchanged from `webhooks/whatsapp.py::_get_or_create_customer`
        (pre-PR-7) — get-or-create, race-safe against
        `uq_customer_business_phone` via a SAVEPOINT so a concurrent
        insert's rollback doesn't discard any other message already
        staged in this same `record_inbound` call."""
        customer = self._db.scalars(
            select(Customer).where(
                Customer.business_id == business_id, Customer.wa_phone == wa_phone
            )
        ).first()
        if customer is not None:
            return customer
        try:
            with self._db.begin_nested():
                customer = Customer(
                    business_id=business_id, wa_phone=wa_phone, display_name=display_name
                )
                self._db.add(customer)
                self._db.flush()
        except IntegrityError:
            customer = self._db.scalars(
                select(Customer).where(
                    Customer.business_id == business_id, Customer.wa_phone == wa_phone
                )
            ).first()
            if customer is None:
                raise
        return customer

    def _get_or_create_conversation(
        self, business_id: uuid.UUID, customer_id: uuid.UUID, now: datetime, channel: str
    ) -> Conversation:
        """Unchanged from `webhooks/whatsapp.py::_get_or_create_conversation`
        (pre-PR-7), plus `channel` (Sprint 65 PR 4) — set only when a new
        Conversation is created; an existing one keeps whatever channel it
        was created with, since a Customer (and therefore its Conversation)
        is single-channel for its whole lifetime by construction (see
        `Conversation.channel`'s own docstring, app/models.py)."""
        conversation = self._db.scalars(
            select(Conversation)
            .where(
                Conversation.business_id == business_id,
                Conversation.customer_id == customer_id,
                Conversation.status == "active",
            )
            .order_by(Conversation.last_message_at.desc().nullslast())
        ).first()
        if conversation is None:
            conversation = Conversation(
                business_id=business_id, customer_id=customer_id, status="active", channel=channel
            )
            self._db.add(conversation)
            self._db.flush()
        return conversation

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

    def _resolve_send_context(
        self, business: Business, customer: Customer, conversation: Conversation
    ) -> _SendContext | None:
        """The one place MessagingService has to know which table a
        channel's credentials live in (Sprint 65 PR 5). Everything else in
        `send_reply()`/`approve_and_send()` stays channel-agnostic — this
        is a narrow, deliberate exception to "no channel-name branching"
        (messaging-platform.md §3), the exact gap that document's own §8
        step 7 / §10 flagged as real, expected work for the first channel
        after WhatsApp, not an architecture change.

        Returns `None` if this conversation's channel has no usable stored
        credential — callers treat that identically to "not connected,"
        same as the pre-PR-5 WhatsApp-only check did.
        """
        if conversation.channel == "whatsapp":
            if not business.whatsapp_phone_number_id:
                return None
            credential = get_stored_whatsapp_credential(self._db, business.id)
            if credential is None:
                return None
            return _SendContext(
                channel="whatsapp",
                external_account_id=business.whatsapp_phone_number_id,
                external_conversation_id=customer.wa_phone,
                access_token=get_whatsapp_access_token(credential),
            )
        if conversation.channel == "instagram":
            credential = get_stored_instagram_credential(self._db, business.id)
            if credential is None:
                return None
            return _SendContext(
                channel="instagram",
                # Meta's Send API is keyed by the connected Page, not the
                # IG business account id — see app/channels/instagram/
                # send.py's module docstring.
                external_account_id=credential.page_id,
                external_conversation_id=customer.wa_phone,
                access_token=get_instagram_access_token(credential),
            )
        return None

    def send_reply(
        self,
        business: Business,
        conversation: Conversation,
        message: Message,
        *,
        sender: Callable[..., str] | None = None,
    ) -> Callable[[], None] | None:
        """Send/execute the reply immediately (Autonomous Mode) and mark
        sent/failed. Replaces `app/ai/processing.py::_auto_send` — every
        line of tool-execution/status-transition logic below is unchanged
        from that function; only `db` (now `self._db`) and `sender`'s
        default (now `self._send`, routing through ChannelManager instead
        of importing a transport function directly) differ.

        `sender` stays an optional override — same escape hatch tests have
        always used to avoid a real network call — defaulting to
        `self._send` (ChannelManager -> registry -> provider) rather than
        a module-level function, since that adapter (`send_via_channel_
        manager`) is retired as of this PR.

        For a proposed calendar action (message.type == "tool_call"), the
        tool executes first — no approval gate in this mode, mirroring how
        a text reply already sends immediately here (DEC-027, extended by
        DEC-032). Runs the tool with commit=False (Section A4) and returns
        the resulting `on_commit_failure` (or None) so the caller's single
        outer commit can compensate if it fails.

        Checked up front, before any tool call: no channel connection
        (phone number/Page or stored credential — see
        `_resolve_send_context()`, Sprint 65 PR 5) or an expired 24-hour
        service window both mean there's no way to notify the customer, so
        nothing here should proceed far enough to need reverting. Mirrors
        `approve_and_send`'s identical up-front checks.

        Every failure branch sets `message.ai_meta["failure_reason"]` — the
        caller uses its presence, not `message.status`, as the "did the
        underlying action fail" signal, since a failed tool call still ends
        with `message.status == "sent"` once its honest fallback text goes
        out (see the tool_call branch below).
        """
        sender = sender or self._send
        customer = self._db.get(Customer, conversation.customer_id)
        send_context = self._resolve_send_context(business, customer, conversation)

        if send_context is None:
            message.status = "failed"
            message.ai_meta = {
                **(message.ai_meta or {}),
                "failure_reason": "channel_not_connected",
            }
            logger.warning(
                "Autonomous send skipped for conversation %s: %s not connected",
                conversation.id,
                _channel_label(conversation.channel),
            )
            return None

        if (
            conversation.window_expires_at is not None
            and datetime.now(timezone.utc).replace(tzinfo=None) > conversation.window_expires_at
        ):
            message.status = "failed"
            message.ai_meta = {
                **(message.ai_meta or {}),
                "failure_reason": "channel_window_expired",
            }
            logger.warning(
                "Autonomous send skipped for conversation %s: %s 24h service window expired",
                conversation.id,
                _channel_label(conversation.channel),
            )
            return None

        if message.type == "tool_call":
            tool_call = ToolCall(
                id="autonomous",
                name=message.ai_meta["tool_name"],
                arguments=message.ai_meta["tool_arguments"],
            )
            # Critical audit fix: no human reviews an Autonomous Mode send,
            # so the only legitimate way a governed tool (e.g.
            # cancel_appointment) may execute here is if *this*
            # conversation already went through governance's confirm-
            # with-the-customer flow in a prior turn. get_pending_action()
            # re-reads the same state app/ai/orchestrator.py::generate_reply()
            # already consulted to build this turn's plan — safe to read
            # again here since nothing writes a new trace for this turn
            # until after this call returns.
            result = execute_tool_call(
                self._db,
                business.id,
                tool_call,
                customer_id=customer.id,
                conversation_id=conversation.id,
                commit=False,
                pending_action=get_pending_action(self._db, conversation.id),
            )
            if result.success:
                message.ai_meta = {**message.ai_meta, "tool_result": result.message}
                # message.body up to this point is still preview_tool_call()'s
                # internal, dashboard-editable text. Autonomous Mode has no
                # human to edit it before send, so it must never go out as-is.
                message.body = confirmation_message_for(tool_call, result)
                on_commit_failure = result.on_commit_failure
            else:
                # The WhatsApp channel itself is fine here (unlike the two
                # branches above), so there's no reason not to tell the
                # customer *something* happened — just never the internal
                # reason why: result.message can read like "This business
                # has not connected a Google Calendar", an operational
                # detail for the founder, not something a customer should
                # see. The real reason is preserved in ai_meta below for
                # the founder (and drives the escalation the caller creates).
                logger.warning(
                    "Autonomous tool call %s failed for conversation %s: %s",
                    tool_call.name,
                    conversation.id,
                    result.message,
                )
                message.ai_meta = {**message.ai_meta, "failure_reason": result.message}
                message.body = AUTONOMOUS_TOOL_FAILURE_TEXT
                on_commit_failure = None
        else:
            on_commit_failure = None

        try:
            wa_message_id = sender(
                send_context.external_account_id,
                send_context.external_conversation_id,
                message.body,
                access_token=send_context.access_token,
                channel=send_context.channel,
                media=message.media,
            )
            message.status = "sent"
            message.wa_message_id = wa_message_id
            logger.info("Autonomously sent reply for conversation %s", conversation.id)
        except WhatsAppSendError:
            # Whatever this row's body was (a real confirmation, or the
            # honest fallback text above) never reached the customer
            # either way — escalate like any other failure. Preserves an
            # existing tool-failure reason if one's already set, rather
            # than overwriting it with the send failure and losing why the
            # turn actually failed.
            message.status = "failed"
            message.ai_meta = {"failure_reason": "channel_send_failed", **(message.ai_meta or {})}
            logger.exception("Autonomous send failed for conversation %s", conversation.id)

        return on_commit_failure

    def approve_and_send(
        self,
        business_id: uuid.UUID,
        message_id: uuid.UUID,
        *,
        sender: Callable[..., str] | None = None,
    ) -> Message:
        """Approve a pending reply: if it's a proposed calendar action
        (message.type == "tool_call" — DEC-032), execute it now, then send
        the (possibly human-edited) confirmation body to the customer and
        mark sent. Replaces `app/services/replies.py::approve_and_send` —
        every line below is unchanged from that function; only `db` (now
        `self._db`) and `sender`'s default (now `self._send`) differ.

        Raises ValueError if the message isn't an approvable pending reply
        for this business. Raises WhatsAppNotConnectedError up front
        (before any tool call or send is attempted; despite the name, this
        covers any channel — see `_resolve_send_context()`, Sprint 65 PR 5)
        if the conversation's channel has no usable stored credential.
        Raises WhatsAppWindowExpiredError (after marking the message failed) if
        the customer's 24-hour service window has closed — checked after
        claiming but before any tool call, so a booking can't execute with
        no way left to tell the customer it happened. Raises CalendarError
        (after marking the message failed) if a proposed tool call fails
        to execute. Raises whatever the send raised (after marking the
        message failed and committing) if the send fails — almost always
        WhatsAppSendError, but this never assumes that's the only
        possibility: once the message is claimed, every exit path leaves
        it in a terminal state before propagating, never stuck at
        "sending".

        Concurrency: claimed via a conditional UPDATE (pending_approval ->
        sending), committed immediately — Postgres's row-level lock
        serializes concurrent claims.

        Atomicity: the tool call executes with commit=False; the single
        commit below persists its effect together with this Message's
        final status/ai_meta/wa_message_id — either both land or neither
        does.
        """
        sender = sender or self._send
        message = get_pending_reply(self._db, business_id, message_id)
        conversation = self._db.get(Conversation, message.conversation_id)
        business = self._db.get(Business, business_id)
        customer = self._db.get(Customer, conversation.customer_id)

        send_context = self._resolve_send_context(business, customer, conversation)
        if send_context is None:
            raise WhatsAppNotConnectedError(
                f"This business has not connected {_channel_label(conversation.channel)} yet"
            )

        claimed = self._db.execute(
            update(Message)
            .where(Message.id == message_id, Message.status == "pending_approval")
            .values(status="sending")
        ).rowcount
        self._db.commit()
        if claimed == 0:
            raise ValueError("Message is not a pending reply for this business")

        if (
            conversation.window_expires_at is not None
            and datetime.now(timezone.utc).replace(tzinfo=None) > conversation.window_expires_at
        ):
            message.status = "failed"
            message.ai_meta = {
                **(message.ai_meta or {}),
                "failure_reason": "channel_window_expired",
            }
            self._db.commit()
            channel_label = _channel_label(conversation.channel)
            logger.warning(
                "%s 24h service window expired for message %s (business %s); not sent",
                channel_label,
                message_id,
                business_id,
            )
            raise WhatsAppWindowExpiredError(
                f"The customer's 24-hour {channel_label} service window has closed. "
                "A template message would be required to reach them now, which isn't "
                "supported yet."
            )

        on_commit_failure = None
        if message.type == "tool_call":
            tool_call = ToolCall(
                id="approved",
                name=message.ai_meta["tool_name"],
                arguments=message.ai_meta["tool_arguments"],
            )
            # A human explicitly clicking Approve on this exact pending
            # tool call *is* the confirmation governance requires
            # (DEC-032/DEC-033 already gate every Assisted-Mode tool call
            # behind this review, governed or not) — human_approved=True
            # satisfies app/ai/tools.py::execute_tool_call's confirmation
            # gate regardless of any conversation-level pending_action
            # state, which may have since moved on if the customer sent
            # more messages while this item sat in the queue.
            result = execute_tool_call(
                self._db,
                business_id,
                tool_call,
                customer_id=customer.id,
                conversation_id=conversation.id,
                commit=False,
                human_approved=True,
            )
            if not result.success:
                message.status = "failed"
                self._db.commit()
                logger.warning(
                    "Approved tool call %s failed for message %s: %s",
                    tool_call.name,
                    message_id,
                    result.message,
                )
                raise CalendarError(result.message)
            message.ai_meta = {**message.ai_meta, "tool_result": result.message}
            on_commit_failure = result.on_commit_failure

        try:
            wa_message_id = sender(
                send_context.external_account_id,
                send_context.external_conversation_id,
                message.body,
                access_token=send_context.access_token,
                channel=send_context.channel,
                media=message.media,
            )
        except Exception:
            # Previously `except WhatsAppSendError` only. This message was
            # already durably committed to status="sending" by the claim
            # step above — the one guarantee this method must never break
            # is that every path out of here leaves the message in a
            # terminal state, not stuck at "sending" forever. Catching
            # broadly (not just WhatsAppSendError) is what makes that a
            # guarantee rather than a best effort: a `sender` this codebase
            # doesn't control (tests inject their own) can always raise
            # something normalization never sees.
            #
            # Reuses the exact compensation this method already applies to
            # its own final commit below rather than a second
            # implementation: if persisting "failed" itself fails, the
            # tool call already executed for real (booked/rescheduled/
            # cancelled on the external calendar) with nothing local
            # pointing to it, so on_commit_failure — set above only when a
            # tool call ran with commit=False — cleans that up before the
            # original exception propagates.
            message.status = "failed"
            message.ai_meta = {**(message.ai_meta or {}), "failure_reason": "channel_send_failed"}
            try:
                self._db.commit()
            except Exception:
                if on_commit_failure is not None:
                    on_commit_failure()
                logger.exception(
                    "Failed to persist failed status for reply %s (business %s) after a "
                    "send error; compensating for any already-executed tool call",
                    message_id,
                    business_id,
                )
                raise
            logger.exception(
                "Failed to send reply %s (business %s); marked failed", message_id, business_id
            )
            raise

        message.status = "sent"
        message.wa_message_id = wa_message_id
        try:
            self._db.commit()
        except Exception:
            if on_commit_failure is not None:
                on_commit_failure()
            raise
        logger.info("Sent reply %s for business %s", message_id, business_id)
        return message

    def _send(
        self,
        external_account_id: str,
        external_conversation_id: str,
        body: str,
        *,
        access_token: str,
        channel: str,
        media: list[dict] | None = None,
    ) -> str:
        """The default `sender`: routes through ChannelManager -> the
        channel registry -> the resolved Provider's send() instead of
        calling a Graph API directly. Replaces the standalone
        `app.services.messaging.send_via_channel_manager()` (Sprint 64A
        PR 6), now private to this class rather than a free function three
        other modules imported — "no remaining adapter layer" (PR 7 scope)
        means this logic has exactly one caller-facing home, not zero
        implementations of it.

        Sprint 65 PR 5: generalized from a WhatsApp-only implementation —
        `channel` (from `_resolve_send_context()`) now selects the DTO tag
        `ChannelManager` resolves a provider from, instead of a hardcoded
        `"whatsapp"` literal. `external_account_id`/`external_conversation_id`
        replace the old `phone_number_id`/`to` parameter names, but keep the
        exact same positional order and kwarg-only `access_token` — every
        existing test-injected `sender` fake already accepts arbitrary
        `**kwargs`, so the new `channel` kwarg is silently absorbed by all
        of them without any test changes needed.

        Sprint 65 PR 6: `media` (the sending Message row's own `.media`
        column — a `list[dict] | None`, see `_serialize_media()`/
        `_deserialize_media()`) threads through the same way — `None`/`[]`
        builds a plain-text `OutboundMessage` exactly as before, so a
        text-only send is byte-for-byte unchanged.

        Preserves the exact contract `send_via_channel_manager` and,
        before it, `send_text` had: raise WhatsAppSendError on any
        failure, return the provider's message id on success — so
        `send_reply`/`approve_and_send` above (and every test injecting
        its own `sender`) need no change to their exception handling.
        """
        message = OutboundMessage(
            channel=channel,
            external_conversation_id=external_conversation_id,
            text=body,
            media=_deserialize_media(media),
        )
        creds = ChannelCredentials(
            channel=channel, access_token=access_token, external_account_id=external_account_id
        )
        try:
            receipt = ChannelManager().send(message, creds)
        except ChannelError as exc:
            raise WhatsAppSendError(str(exc)) from exc
        if receipt.status == "failed":
            raise WhatsAppSendError(receipt.error or f"{_channel_label(channel)} send failed")
        assert receipt.external_message_id is not None  # invariant when status == "sent"
        return receipt.external_message_id
