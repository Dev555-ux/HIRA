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

from app.ai.llm.base import ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.tools import execute_tool_call, response_to_message_fields
from app.db.session import SessionLocal
from app.models import Business, Conversation, Customer, Message
from app.services.messaging import WhatsAppSendError, send_text

logger = logging.getLogger(__name__)


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

        response, retrieved = generate_reply(db, conversation, user_text)
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
        if business is not None and business.mode == "autonomous":
            _auto_send(db, business, conversation, message, sender)

        db.commit()
        logger.info("Stored reply for conversation %s (status=%s)", conversation_id, message.status)
    except Exception:
        logger.exception("Failed to generate reply for conversation %s", conversation_id)
        db.rollback()
    finally:
        db.close()


def _auto_send(
    db,
    business: Business,
    conversation: Conversation,
    message: Message,
    sender: Callable[[str, str, str], str],
) -> None:
    """Send/execute the reply immediately (Autonomous Mode) and mark sent/failed.

    For a proposed calendar action (message.type == "tool_call"), the tool
    executes first — no approval gate in this mode, mirroring how a text
    reply already sends immediately here (DEC-027, extended by DEC-032).
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
        )
        if not result.success:
            message.status = "failed"
            logger.warning(
                "Autonomous tool call %s failed for conversation %s: %s",
                tool_call.name,
                conversation.id,
                result.message,
            )
            return
        message.ai_meta = {**message.ai_meta, "tool_result": result.message}

    try:
        wa_message_id = sender(business.whatsapp_phone_number_id, customer.wa_phone, message.body)
        message.status = "sent"
        message.wa_message_id = wa_message_id
        logger.info("Autonomously sent reply for conversation %s", conversation.id)
    except WhatsAppSendError:
        message.status = "failed"
        logger.exception("Autonomous send failed for conversation %s", conversation.id)
