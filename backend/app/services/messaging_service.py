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
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.llm.base import ToolCall
from app.ai.tools import confirmation_message_for, execute_tool_call
from app.calendar.providers.base import CalendarError
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import ChannelError
from app.channels.base.message import NormalizedMessage, OutboundMessage
from app.core.config import settings
from app.jobs import enqueue_job
from app.models import Business, Conversation, Customer, Message
from app.services.channel_manager import ChannelManager
from app.services.execution_traces import get_pending_action
from app.services.messaging import WhatsAppNotConnectedError, WhatsAppSendError
from app.services.replies import get_pending_reply
from app.whatsapp.credentials import get_access_token, get_stored_credential

logger = logging.getLogger(__name__)

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


class WhatsAppWindowExpiredError(RuntimeError):
    """The customer's 24-hour WhatsApp service window has closed — a
    free-form text send would violate Meta's platform rules (a template
    message would be required instead, not yet supported). Raised before
    any tool call or send is attempted, same as WhatsAppNotConnectedError,
    so a booking can't execute with no way left to notify the customer it
    happened. Relocated from app/services/replies.py in Sprint 64A PR 7 —
    same class, same meaning, moved alongside approve_and_send()."""


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
        now = datetime.now(UTC)
        for normalized in messages:
            # Read straight from the original native payload (carried
            # unchanged on `.raw`) for these two fields — see PR 5's
            # identical note in the code this replaces: NormalizedMessage's
            # own external_message_id/external_sender_id default a missing
            # value to "", while this dedupe/lookup logic has always relied
            # on a missing value being None. Unreachable in practice (the
            # platform always sends both), kept byte-for-byte anyway.
            wa_message_id = normalized.raw.get("id")
            already = self._db.scalars(
                select(Message).where(Message.wa_message_id == wa_message_id)
            ).first()
            if already is not None:
                continue  # dedupe

            wa_phone = normalized.raw.get("from")
            customer = self._get_or_create_customer(
                business_id, wa_phone, normalized.sender_display_name
            )
            conversation = self._get_or_create_conversation(business_id, customer.id, now)

            body = normalized.text
            message = Message(
                conversation_id=conversation.id,
                business_id=business_id,
                direction="inbound",
                wa_message_id=wa_message_id,
                body=body,
                type=normalized.raw.get("type", "text"),
                status="received",
            )
            self._db.add(message)
            self._db.flush()
            conversation.last_message_at = now
            conversation.window_expires_at = now + SERVICE_WINDOW

            # Sprint 73: capture the Click-to-WhatsApp click id the first
            # (and only) time Meta sends it. Never overwritten — a later
            # message in the same thread carries no referral object, and if
            # a customer somehow re-enters through a second ad, the click
            # that actually opened this conversation is the one Meta
            # attributes against.
            if conversation.ctwa_clid is None and normalized.ctwa_clid:
                conversation.ctwa_clid = normalized.ctwa_clid

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
        self, business_id: uuid.UUID, customer_id: uuid.UUID, now: datetime
    ) -> Conversation:
        """Unchanged from `webhooks/whatsapp.py::_get_or_create_conversation`
        (pre-PR-7)."""
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
                business_id=business_id, customer_id=customer_id, status="active"
            )
            self._db.add(conversation)
            self._db.flush()
        return conversation

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------

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

        Checked up front, before any tool call: no WhatsApp connection
        (phone number or stored credential) or an expired 24-hour service
        window both mean there's no way to notify the customer, so nothing
        here should proceed far enough to need reverting. Mirrors
        `approve_and_send`'s identical up-front checks.

        Every failure branch sets `message.ai_meta["failure_reason"]` — the
        caller uses its presence, not `message.status`, as the "did the
        underlying action fail" signal, since a failed tool call still ends
        with `message.status == "sent"` once its honest fallback text goes
        out (see the tool_call branch below).
        """
        sender = sender or self._send
        customer = self._db.get(Customer, conversation.customer_id)
        credential = get_stored_credential(self._db, business.id)

        if not business.whatsapp_phone_number_id or credential is None:
            message.status = "failed"
            message.ai_meta = {
                **(message.ai_meta or {}),
                "failure_reason": "whatsapp_not_connected",
            }
            logger.warning(
                "Autonomous send skipped for conversation %s: WhatsApp not connected",
                conversation.id,
            )
            return None

        if (
            conversation.window_expires_at is not None
            and datetime.now(UTC).replace(tzinfo=None) > conversation.window_expires_at
        ):
            message.status = "failed"
            message.ai_meta = {
                **(message.ai_meta or {}),
                "failure_reason": "whatsapp_window_expired",
            }
            logger.warning(
                "Autonomous send skipped for conversation %s: WhatsApp 24h service window expired",
                conversation.id,
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
                business.whatsapp_phone_number_id,
                customer.wa_phone,
                message.body,
                access_token=get_access_token(credential),
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
            message.ai_meta = {"failure_reason": "whatsapp_send_failed", **(message.ai_meta or {})}
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
        (before any tool call or send is attempted) if the business has no
        WhatsApp number/credentials configured. Raises
        WhatsAppWindowExpiredError (after marking the message failed) if
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

        if not business.whatsapp_phone_number_id:
            raise WhatsAppNotConnectedError("This business has not connected WhatsApp yet")
        credential = get_stored_credential(self._db, business_id)
        if credential is None:
            raise WhatsAppNotConnectedError("This business has not connected WhatsApp yet")

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
            and datetime.now(UTC).replace(tzinfo=None) > conversation.window_expires_at
        ):
            message.status = "failed"
            message.ai_meta = {
                **(message.ai_meta or {}),
                "failure_reason": "whatsapp_window_expired",
            }
            self._db.commit()
            logger.warning(
                "WhatsApp 24h service window expired for message %s (business %s); not sent",
                message_id,
                business_id,
            )
            raise WhatsAppWindowExpiredError(
                "The customer's 24-hour WhatsApp service window has closed. "
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
                business.whatsapp_phone_number_id,
                customer.wa_phone,
                message.body,
                access_token=get_access_token(credential),
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
            message.ai_meta = {**(message.ai_meta or {}), "failure_reason": "whatsapp_send_failed"}
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

    def _send(self, phone_number_id: str, to: str, body: str, *, access_token: str) -> str:
        """The default `sender`: routes through ChannelManager -> the
        channel registry -> WhatsAppProvider.send() instead of calling the
        Graph API directly. Replaces the standalone
        `app.services.messaging.send_via_channel_manager()` (Sprint 64A
        PR 6), now private to this class rather than a free function three
        other modules imported — "no remaining adapter layer" (PR 7 scope)
        means this logic has exactly one caller-facing home, not zero
        implementations of it.

        Preserves the exact contract `send_via_channel_manager` and,
        before it, `send_text` had: raise WhatsAppSendError on any
        failure, return the provider's message id on success — so
        `send_reply`/`approve_and_send` above (and every test injecting
        its own `sender`) need no change to their exception handling.
        """
        message = OutboundMessage(channel="whatsapp", external_conversation_id=to, text=body)
        creds = ChannelCredentials(
            channel="whatsapp", access_token=access_token, external_account_id=phone_number_id
        )
        try:
            receipt = ChannelManager().send(message, creds)
        except ChannelError as exc:
            raise WhatsAppSendError(str(exc)) from exc
        if receipt.status == "failed":
            raise WhatsAppSendError(receipt.error or "WhatsApp send failed")
        assert receipt.external_message_id is not None  # invariant when status == "sent"
        return receipt.external_message_id
