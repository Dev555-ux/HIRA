"""Background processing of inbound messages.

Runs after the webhook has acknowledged (so Meta isn't kept waiting): loads the
conversation, generates a grounded reply via the orchestrator, and stores it as
an outbound message in `pending_approval` status (Assisted Mode — a human
approves before it is actually sent). Sending is a separate, later step.

Opens its own DB session because it runs outside the request lifecycle.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
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
        message = Message(
            conversation_id=conversation.id,
            business_id=conversation.business_id,
            direction="outbound",
            body=response.text,
            type="text",
            status="pending_approval",
            ai_meta={
                "model": response.model,
                "prompt_version": SYSTEM_PROMPT_VERSION,
                "retrieved_count": len(retrieved),
            },
        )
        db.add(message)
        db.flush()

        # Autonomous Mode: send immediately with no human approval. Assisted Mode
        # (the default) leaves the reply as pending_approval for the dashboard.
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
    """Send the reply via the WhatsApp Cloud API and mark it sent/failed."""
    customer = db.get(Customer, conversation.customer_id)
    try:
        wa_message_id = sender(business.whatsapp_phone_number_id, customer.wa_phone, message.body)
        message.status = "sent"
        message.wa_message_id = wa_message_id
        logger.info("Autonomously sent reply for conversation %s", conversation.id)
    except WhatsAppSendError:
        message.status = "failed"
        logger.exception("Autonomous send failed for conversation %s", conversation.id)
