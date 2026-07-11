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

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.llm import LLMProvider
from app.ai.llm.base import ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.tools import execute_tool_call, response_to_message_fields
from app.calendar.providers.base import CalendarError
from app.db.tenant import get_scoped
from app.models import Business, Conversation, Customer, Escalation, Message
from app.services.messaging import WhatsAppNotConnectedError, WhatsAppSendError, send_text

logger = logging.getLogger(__name__)


def _get_pending_reply(db: Session, business_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    """Fetch a message, but only if it's this business's editable pending reply."""
    message = get_scoped(db, Message, business_id, message_id)
    if message is None or message.direction != "outbound" or message.status != "pending_approval":
        raise ValueError("Message is not a pending reply for this business")
    return message


def approve_and_send(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    sender: Callable[[str, str, str], str] = send_text,
) -> Message:
    """Approve a pending reply: if it's a proposed calendar action
    (message.type == "tool_call" — DEC-032), execute it now, then send the
    (possibly human-edited) confirmation body to the customer and mark sent.

    Raises ValueError if the message isn't an approvable pending reply for this
    business. Raises WhatsAppNotConnectedError up front (before any tool call
    or send is attempted) if the business has no WhatsApp number configured —
    approving a tool_call message would otherwise execute a real side effect
    (e.g. book a calendar slot) with no way to actually notify the customer.
    Raises CalendarError (after marking the message failed) if a proposed
    tool call fails to execute (e.g. the slot was taken meanwhile). Raises
    WhatsAppSendError (after marking the message failed) if the send fails.

    Concurrency: two requests approving the same message race between this
    load and the eventual commit. Before any side effect (tool execution or
    WhatsApp send), the message is claimed with a conditional UPDATE
    (pending_approval -> sending) and committed immediately. Postgres's
    row-level lock on that UPDATE serializes concurrent claims: only one
    commits pending_approval -> sending, the other's identical UPDATE then
    matches zero rows and raises ValueError here, before touching the
    calendar or WhatsApp.
    """
    message = _get_pending_reply(db, business_id, message_id)
    conversation = db.get(Conversation, message.conversation_id)
    business = db.get(Business, business_id)
    customer = db.get(Customer, conversation.customer_id)

    if not business.whatsapp_phone_number_id:
        raise WhatsAppNotConnectedError("This business has not connected WhatsApp yet")

    claimed = db.execute(
        update(Message)
        .where(Message.id == message_id, Message.status == "pending_approval")
        .values(status="sending")
    ).rowcount
    db.commit()
    if claimed == 0:
        raise ValueError("Message is not a pending reply for this business")

    if message.type == "tool_call":
        tool_call = ToolCall(
            id="approved",
            name=message.ai_meta["tool_name"],
            arguments=message.ai_meta["tool_arguments"],
        )
        result = execute_tool_call(
            db, business_id, tool_call, customer_id=customer.id, conversation_id=conversation.id
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

    try:
        wa_message_id = sender(business.whatsapp_phone_number_id, customer.wa_phone, message.body)
    except WhatsAppSendError:
        message.status = "failed"
        db.commit()
        logger.exception("Failed to send reply %s; marked failed", message_id)
        raise

    message.status = "sent"
    message.wa_message_id = wa_message_id
    db.commit()
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

    response, retrieved = generate_reply(
        db, conversation, user_message.body, llm=llm, embedding=embedding
    )
    message_type, body, extra_ai_meta = response_to_message_fields(response)
    message.type = message_type
    message.body = body
    message.ai_meta = {
        "model": response.model,
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "retrieved_count": len(retrieved),
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
