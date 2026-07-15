"""Background processing of inbound messages.

Runs after the webhook has acknowledged (so Meta isn't kept waiting): loads the
conversation, generates a grounded reply via the orchestrator, and stores it as
an outbound message in `pending_approval` status (Assisted Mode — a human
approves before it is actually sent, or before a proposed calendar action
executes — see DEC-032). Sending/executing is a separate, later step.

Opens its own DB session because it runs outside the request lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from app.ai.llm.base import LLMResponse, ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.tools import confirmation_message_for, execute_tool_call, response_to_message_fields
from app.db.session import SessionLocal
from app.models import Business, Conversation, Customer, Escalation, Message
from app.services.messaging import WhatsAppSendError, send_text

logger = logging.getLogger(__name__)

# AI-3: app/webhooks/whatsapp.py::_extract_text collapses any non-text
# inbound message (image/audio/video/location/...) to "" — there is nothing
# for the LLM to ground a reply on. Rather than calling the orchestrator on
# an empty string (previously: an ungrounded, unpredictable reply) this is
# drafted directly, through the same pending_approval/auto-send pipeline a
# real AI reply goes through.
NON_TEXT_FALLBACK_TEXT = (
    "Thanks for your message! I can currently only read text — could you type that out for me?"
)


def generate_and_store_reply(
    conversation_id: uuid.UUID,
    user_text: str,
    *,
    sender: Callable[[str, str, str], str] = send_text,
) -> None:
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            logger.warning("Conversation %s not found; skipping reply", conversation_id)
            return

        # REL-2: a failure here (the LLM call itself) is the one this sprint's
        # fallback covers — nothing has been written yet, so there's a clean
        # rollback + escalate. A failure *after* this point (send/commit) has
        # its own atomicity handling below (on_commit_failure) and is left to
        # the outer except unchanged, so it isn't double-escalated on top of
        # that already-tested compensation path.
        try:
            if user_text.strip():
                response, retrieved = generate_reply(db, conversation, user_text)
            else:
                response, retrieved = LLMResponse(text=NON_TEXT_FALLBACK_TEXT, model="none"), []
        except Exception:
            logger.exception("Failed to generate reply for conversation %s", conversation_id)
            db.rollback()
            try:
                _store_failure_escalation(db, conversation_id)
            except Exception:
                logger.exception(
                    "Failed to record fallback escalation for conversation %s", conversation_id
                )
                db.rollback()
            return

        business = db.get(Business, conversation.business_id)

        message_type, body, extra_ai_meta = response_to_message_fields(response)
        message = Message(
            conversation_id=conversation.id,
            business_id=conversation.business_id,
            direction="outbound",
            body=body,
            type=message_type,
            status="pending_approval",
            ai_meta={
                "model": response.model,
                "prompt_version": SYSTEM_PROMPT_VERSION,
                "retrieved_count": len(retrieved),
                **extra_ai_meta,
            },
        )
        db.add(message)
        db.flush()

        # Autonomous Mode: send/execute immediately with no human approval.
        # Assisted Mode (the default) leaves the reply/proposed action as
        # pending_approval for the dashboard.
        on_commit_failure = None
        if business is not None and business.mode == "autonomous":
            on_commit_failure = _auto_send(db, business, conversation, message, sender)

        # Section A4: _auto_send ran any tool call with commit=False, so its
        # effect (e.g. the Appointment row) is only flushed. This commit is
        # what durably persists that effect together with the Message row
        # (creation + status/ai_meta/body/wa_message_id) — either both land
        # or neither does. On failure, on_commit_failure (if set) deletes the
        # now-orphaned external calendar event before re-raising, to be
        # caught by the except below like any other failure here.
        try:
            db.commit()
        except Exception:
            if on_commit_failure is not None:
                on_commit_failure()
            raise
        logger.info("Stored reply for conversation %s (status=%s)", conversation_id, message.status)
    except Exception:
        logger.exception("Failed to generate reply for conversation %s", conversation_id)
        db.rollback()
    finally:
        db.close()


def _store_failure_escalation(db, conversation_id: uuid.UUID) -> None:
    """REL-2: on an AI generation failure, the old behavior left zero trace —
    no Message row, no signal anywhere a human would look, customer met with
    silence. This reuses the exact mechanism a human already uses to flag a
    conversation (app/services/replies.py::escalate_reply — same "escalated"
    Message/Conversation status, same Escalation row, already rendered by the
    dashboard's Inbox), just triggered by a system failure instead of a
    person clicking Escalate. reason="external_failure" is one of
    Escalation.reason's existing documented values (app/models.py), not a
    new one invented for this.
    """
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        return
    message = Message(
        conversation_id=conversation.id,
        business_id=conversation.business_id,
        direction="outbound",
        body=(
            "HIRA couldn't generate a reply to this message due to a temporary issue. "
            "This conversation has been flagged for you to follow up manually."
        ),
        type="text",
        status="escalated",
    )
    db.add(message)
    conversation.status = "escalated"
    db.add(
        Escalation(
            business_id=conversation.business_id,
            conversation_id=conversation.id,
            reason="external_failure",
            status="open",
        )
    )
    db.commit()


def _auto_send(
    db,
    business: Business,
    conversation: Conversation,
    message: Message,
    sender: Callable[[str, str, str], str],
) -> Callable[[], None] | None:
    """Send/execute the reply immediately (Autonomous Mode) and mark sent/failed.

    For a proposed calendar action (message.type == "tool_call"), the tool
    executes first — no approval gate in this mode, mirroring how a text
    reply already sends immediately here (DEC-027, extended by DEC-032).

    Runs the tool with commit=False (Section A4) and returns the resulting
    `on_commit_failure` (or None) so the caller's single outer commit can
    compensate if it fails — see generate_and_store_reply.
    """
    customer = db.get(Customer, conversation.customer_id)

    if message.type == "tool_call":
        tool_call = ToolCall(
            id="autonomous",
            name=message.ai_meta["tool_name"],
            arguments=message.ai_meta["tool_arguments"],
        )
        result = execute_tool_call(
            db,
            business.id,
            tool_call,
            customer_id=customer.id,
            conversation_id=conversation.id,
            commit=False,
        )
        if not result.success:
            message.status = "failed"
            logger.warning(
                "Autonomous tool call %s failed for conversation %s: %s",
                tool_call.name,
                conversation.id,
                result.message,
            )
            return None
        message.ai_meta = {**message.ai_meta, "tool_result": result.message}
        # Section A1 fix: message.body up to this point is still
        # preview_tool_call()'s internal, dashboard-editable text (set at
        # creation in response_to_message_fields). Autonomous Mode has no
        # human to edit it before send, so it must never go out as-is.
        message.body = confirmation_message_for(tool_call, result)
        on_commit_failure = result.on_commit_failure
    else:
        on_commit_failure = None

    try:
        wa_message_id = sender(business.whatsapp_phone_number_id, customer.wa_phone, message.body)
        message.status = "sent"
        message.wa_message_id = wa_message_id
        logger.info("Autonomously sent reply for conversation %s", conversation.id)
    except WhatsAppSendError:
        message.status = "failed"
        logger.exception("Autonomous send failed for conversation %s", conversation.id)

    return on_commit_failure
