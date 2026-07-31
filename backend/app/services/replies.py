"""Assisted-Mode actions on a pending AI-drafted reply.

Assisted Mode stores AI-generated replies as outbound `pending_approval`
messages. This module holds every action a human can take on one before it
reaches (or instead of reaching) the customer: approve & send, edit, reject,
regenerate, or escalate to a human.

Every function is tenant-scoped by `business_id` via `get_scoped`/`_get_pending_reply`
and raises `ValueError` if the message doesn't exist, belongs to another
business, or is no longer an editable pending reply (already sent, rejected,
escalated, etc.) — the API layer turns that into a 404, same as the original
approve endpoint, so a wrong-tenant message and a non-existent one look
identical to the caller.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.llm import LLMProvider
from app.ai.llm.base import ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.roles import RECEPTIONIST, role_for_tool
from app.ai.tools import execute_tool_call, response_to_message_fields
from app.calendar.providers.base import CalendarError
from app.db.tenant import get_scoped
from app.models import Business, Conversation, Customer, Escalation, Message
from app.services.messaging import WhatsAppNotConnectedError, WhatsAppSendError, send_text
from app.whatsapp.credentials import get_access_token, get_stored_credential


class WhatsAppWindowExpiredError(RuntimeError):
    """The customer's 24-hour WhatsApp service window has closed — a
    free-form text send would violate Meta's platform rules (a template
    message would be required instead, not yet supported). Raised before
    any tool call or send is attempted, same as WhatsAppNotConnectedError
    above it, so a booking can't execute with no way left to notify the
    customer it happened."""


logger = logging.getLogger(__name__)


def _get_pending_reply(db: Session, business_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    """Fetch a message, but only if it's this business's editable pending reply."""
    message = get_scoped(db, Message, business_id, message_id)
    if message is None or message.direction != "outbound" or message.status != "pending_approval":
        raise ValueError("Message is not a pending reply for this business")
    return message


def send_human_reply(
    db: Session,
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    *,
    body: str,
    sender: Callable[..., str] = send_text,
) -> Message:
    """Send an auditable human-authored reply in an escalated conversation."""
    conversation = get_scoped(db, Conversation, business_id, conversation_id)
    if conversation is None or conversation.status != "escalated":
        raise ValueError("Conversation is not an escalated conversation for this business")

    business = db.get(Business, business_id)
    customer = db.get(Customer, conversation.customer_id)
    if not business.whatsapp_phone_number_id or get_stored_credential(db, business_id) is None:
        raise WhatsAppNotConnectedError("This business has not connected WhatsApp yet")
    if (
        conversation.window_expires_at is not None
        and datetime.now(timezone.utc).replace(tzinfo=None) > conversation.window_expires_at
    ):
        raise WhatsAppWindowExpiredError(
            "The customer's 24-hour WhatsApp service window has closed. "
            "A template message would be required to reach them now, which isn't supported yet."
        )

    message = Message(
        conversation_id=conversation.id,
        business_id=business_id,
        direction="outbound",
        body=body,
        type="text",
        status="sending",
        ai_meta={"sent_by": "human"},
    )
    db.add(message)
    db.commit()

    try:
        message.wa_message_id = sender(
            business.whatsapp_phone_number_id,
            customer.wa_phone,
            message.body,
            access_token=get_access_token(get_stored_credential(db, business_id)),
        )
    except WhatsAppSendError:
        message.status = "failed"
        db.commit()
        logger.exception("Failed to send human reply %s", message.id)
        raise

    message.status = "sent"
    db.commit()
    logger.info("Sent human reply %s for business %s", message.id, business_id)
    return message


def approve_and_send(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    sender: Callable[..., str] = send_text,
) -> Message:
    """Approve a pending reply: if it's a proposed calendar action
    (message.type == "tool_call" — DEC-032), execute it now, then send the
    (possibly human-edited) confirmation body to the customer and mark sent.

    Raises ValueError if the message isn't an approvable pending reply for this
    business. Raises WhatsAppNotConnectedError up front (before any tool call
    or send is attempted) if the business has no WhatsApp number/credentials
    configured — approving a tool_call message would otherwise execute a real
    side effect (e.g. book a calendar slot) with no way to actually notify the
    customer. Raises WhatsAppWindowExpiredError (Sprint 69, after marking the
    message failed) if the customer's 24-hour service window has closed —
    checked after claiming but before any tool call, so a booking can't
    execute with no way left to tell the customer it happened. Raises
    CalendarError (after marking the message failed) if a proposed tool call
    fails to execute (e.g. the slot was taken meanwhile). Raises
    WhatsAppSendError (after marking the message failed) if the send fails.

    Concurrency: two requests approving the same message race between this
    load and the eventual commit. Before any side effect (tool execution or
    WhatsApp send), the message is claimed with a conditional UPDATE
    (pending_approval -> sending) and committed immediately. Postgres's
    row-level lock on that UPDATE serializes concurrent claims: only one
    commits pending_approval -> sending, the other's identical UPDATE then
    matches zero rows and raises ValueError here, before touching the
    calendar or WhatsApp.

    Atomicity (Section A4): the tool call executes with commit=False, so its
    effect (e.g. the Appointment row) is only flushed, not committed. The
    single commit below is what durably persists that effect together with
    this Message's final status/ai_meta/wa_message_id — either both land or
    neither does. If that commit fails, `result.on_commit_failure` (set by
    execute_tool_call when it ran with commit=False) deletes the now-orphaned
    external calendar event before the original exception is re-raised.
    """
    message = _get_pending_reply(db, business_id, message_id)
    conversation = db.get(Conversation, message.conversation_id)
    business = db.get(Business, business_id)
    customer = db.get(Customer, conversation.customer_id)

    if not business.whatsapp_phone_number_id:
        raise WhatsAppNotConnectedError("This business has not connected WhatsApp yet")
    credential = get_stored_credential(db, business_id)
    if credential is None:
        raise WhatsAppNotConnectedError("This business has not connected WhatsApp yet")

    claimed = db.execute(
        update(Message)
        .where(Message.id == message_id, Message.status == "pending_approval")
        .values(status="sending")
    ).rowcount
    db.commit()
    if claimed == 0:
        raise ValueError("Message is not a pending reply for this business")

    if (
        conversation.window_expires_at is not None
        and datetime.now(timezone.utc).replace(tzinfo=None) > conversation.window_expires_at
    ):
        message.status = "failed"
        message.ai_meta = {**(message.ai_meta or {}), "failure_reason": "whatsapp_window_expired"}
        db.commit()
        logger.warning(
            "WhatsApp 24h service window expired for message %s (business %s); not sent",
            message_id,
            business_id,
        )
        raise WhatsAppWindowExpiredError(
            "The customer's 24-hour WhatsApp service window has closed. "
            "A template message would be required to reach them now, which isn't supported yet."
        )

    on_commit_failure = None
    if message.type == "tool_call":
        tool_call = ToolCall(
            id="approved",
            name=message.ai_meta["tool_name"],
            arguments=message.ai_meta["tool_arguments"],
        )
        result = execute_tool_call(
            db,
            business_id,
            tool_call,
            customer_id=customer.id,
            conversation_id=conversation.id,
            commit=False,
        )
        if not result.success:
            message.status = "failed"
            db.commit()
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
    except WhatsAppSendError:
        message.status = "failed"
        db.commit()
        logger.exception("Failed to send reply %s; marked failed", message_id)
        raise

    message.status = "sent"
    message.wa_message_id = wa_message_id
    try:
        db.commit()
    except Exception:
        if on_commit_failure is not None:
            on_commit_failure()
        raise
    logger.info("Sent reply %s for business %s", message_id, business_id)
    return message


def update_draft(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    body: str,
) -> Message:
    """Edit a pending AI draft's text before approval.

    Raises ValueError if the message isn't an editable pending reply for this
    business (including if it has already been approved/sent).
    """
    message = _get_pending_reply(db, business_id, message_id)
    message.body = body
    db.commit()
    logger.info("Edited draft %s for business %s", message_id, business_id)
    return message


def reject_reply(db: Session, business_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    """Reject a pending reply: it is removed from the pending queue and never sent.

    Raises ValueError if the message isn't a pending reply for this business.
    """
    message = _get_pending_reply(db, business_id, message_id)
    message.status = "rejected"
    db.commit()
    logger.info("Rejected reply %s for business %s", message_id, business_id)
    return message


def _last_inbound_before(db: Session, conversation_id: uuid.UUID, before) -> Message | None:
    """The most recent customer message up to a given timestamp in a conversation.

    Uses <= rather than < because Postgres's `now()` (used for `created_at`'s
    server default) is fixed for the duration of a transaction — an inbound
    message and the outbound draft it triggered can legitimately share the same
    timestamp if both were written without an intervening commit. Safe to
    include ties here since this is already filtered to `direction == "inbound"`,
    so it can never match the (outbound) draft itself.
    """
    return db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == "inbound",
            Message.created_at <= before,
        )
        .order_by(Message.created_at.desc())
    ).first()


def regenerate_draft(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
) -> Message:
    """Regenerate a pending draft's text via the unmodified `generate_reply` pipeline.

    Replaces only this message's body/ai_meta — conversation history and the
    approval workflow are untouched. Raises ValueError if the message isn't a
    pending reply for this business, or if there's no customer message left to
    respond to (the draft's own inbound trigger message would have to have been
    deleted, which nothing in the app does today).
    """
    message = _get_pending_reply(db, business_id, message_id)
    conversation = db.get(Conversation, message.conversation_id)

    user_message = _last_inbound_before(db, conversation.id, message.created_at)
    if user_message is None:
        raise ValueError("No customer message found to regenerate a reply for")

    # The plan generate_reply() used isn't traced here — regenerate replaces
    # an existing Message in place rather than starting a new turn, and
    # Sprint 76 deliberately keeps this module untouched by execution
    # tracing (see app/services/execution_traces.py's docstring).
    response, retrieved, _plan = generate_reply(
        db, conversation, user_message.body, llm=llm, embedding=embedding
    )
    # Sprint 74 Phase 1 (DEC-043): response_to_message_fields() can return up
    # to two entries now, but regenerate replaces exactly one already-
    # existing Message in place — there's no second row to spawn here. Only
    # the first (primary) proposed action is used; a second action the model
    # proposed on regeneration is silently dropped, a deliberate, narrow
    # Phase 1 scope limit for this rare, explicit, human-triggered action
    # (not the primary path multi-action collaboration targets).
    message_type, body, extra_ai_meta = response_to_message_fields(response)[0]
    tool_name = extra_ai_meta.get("tool_name")
    message.type = message_type
    message.body = body
    message.ai_meta = {
        "model": response.model,
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "retrieved_count": len(retrieved),
        "agent_role": role_for_tool(tool_name) if tool_name else RECEPTIONIST,
        "regenerated": True,
        **extra_ai_meta,
    }
    db.commit()
    logger.info("Regenerated draft %s for business %s", message_id, business_id)
    return message


def escalate_reply(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    reason: str = "other",
) -> tuple[Message, Escalation]:
    """Escalate a pending reply to a human.

    Removes the message from the pending queue (status -> "escalated"), marks
    the conversation "escalated" (an existing, previously-unused Conversation
    status), and opens an Escalation row — conversation history is untouched.
    Raises ValueError if the message isn't a pending reply for this business.
    """
    message = _get_pending_reply(db, business_id, message_id)
    conversation = db.get(Conversation, message.conversation_id)

    message.status = "escalated"
    conversation.status = "escalated"
    escalation = Escalation(
        business_id=business_id,
        conversation_id=conversation.id,
        reason=reason,
        status="open",
    )
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    logger.info("Escalated reply %s for business %s", message_id, business_id)
    return message, escalation
