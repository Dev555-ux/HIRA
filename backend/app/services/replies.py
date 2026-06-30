"""Approve and send a pending AI reply.

Assisted Mode stores AI-generated replies as outbound `pending_approval`
messages. This closes the loop: on approval, send the reply to the customer via
WhatsApp and mark it `sent` (or `failed` if the send errors).

Tenant-scoped by `business_id` (a business can only approve its own messages).
The sender is injectable for testing.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.db.tenant import get_scoped
from app.models import Business, Conversation, Customer, Message
from app.services.messaging import WhatsAppSendError, send_text

logger = logging.getLogger(__name__)


def approve_and_send(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    sender: Callable[[str, str, str], str] = send_text,
) -> Message:
    """Send a pending outbound reply to the customer and mark it sent.

    Raises ValueError if the message isn't an approvable pending reply for this
    business. Raises WhatsAppSendError (after marking the message failed) if the
    send fails.
    """
    message = get_scoped(db, Message, business_id, message_id)
    if message is None or message.direction != "outbound" or message.status != "pending_approval":
        raise ValueError("Message is not an approvable pending reply for this business")

    conversation = db.get(Conversation, message.conversation_id)
    business = db.get(Business, business_id)
    customer = db.get(Customer, conversation.customer_id)

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
