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

from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.db.session import SessionLocal
from app.models import Conversation, Message

logger = logging.getLogger(__name__)


def generate_and_store_reply(conversation_id: uuid.UUID, user_text: str) -> None:
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            logger.warning("Conversation %s not found; skipping reply", conversation_id)
            return

        response, retrieved = generate_reply(db, conversation, user_text)
        db.add(
            Message(
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
        )
        db.commit()
        logger.info("Stored pending reply for conversation %s", conversation_id)
    except Exception:
        logger.exception("Failed to generate reply for conversation %s", conversation_id)
        db.rollback()
    finally:
        db.close()
