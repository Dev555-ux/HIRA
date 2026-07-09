"""Memory service — conversation-summary persistence (DEC-034).

`app/ai/orchestrator.py`'s raw history window (`HISTORY_LIMIT` messages) is
fed to the LLM verbatim, in full fidelity. Anything older than that window
would otherwise be lost turn over turn. This module is the one place that
"memory" of the older prefix is generated and stored, on `Conversation.summary`
(+ the `summary_message_count` watermark) — see DEC-034 for why a persisted
column was chosen over recomputing on every turn.

Regeneration is bounded: it only happens when the raw window's boundary has
actually advanced past what's already summarized (roughly once every
HISTORY_LIMIT new messages), not on every call. A summarization failure never
blocks the main reply — it's caught and logged, and the previous summary
(possibly None) is returned unchanged.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm import ChatMessage, LLMError, LLMProvider, get_llm_provider
from app.models import Conversation, Message

logger = logging.getLogger(__name__)

# The raw history window size (app/ai/context.py::load_history) a summary
# needs to cover everything *older* than. Defined here since this module is
# the one thing that actually depends on its value; context.py imports it.
HISTORY_LIMIT = 20

_SUMMARY_SYSTEM_PROMPT = """\
Summarize the following WhatsApp conversation between a customer and a \
business's AI receptionist, in 3-5 concise sentences. Capture concrete facts \
only: what the customer wants, any commitments made, decisions reached, and \
open questions. Do not invent anything not present in the transcript."""


def _count_messages(db: Session, conversation_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
    )


def _format_transcript(messages: list[Message]) -> str:
    return "\n".join(
        f"{'Customer' if m.direction == 'inbound' else 'Business'}: {m.body}"
        for m in messages
        if m.body
    )


def get_conversation_summary(
    db: Session, conversation: Conversation, *, llm: LLMProvider | None = None
) -> str | None:
    """The conversation's up-to-date summary of everything older than the raw
    history window, regenerating it first if the window has advanced past
    what's already covered. Returns the existing (possibly None) summary
    unchanged if nothing needs regenerating, or if regeneration fails."""
    total = _count_messages(db, conversation.id)
    older_count = total - HISTORY_LIMIT
    if older_count <= 0:
        return conversation.summary

    if (
        conversation.summary_message_count is not None
        and conversation.summary_message_count >= older_count
    ):
        return conversation.summary

    older_messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
        .limit(older_count)
    ).all()
    transcript = _format_transcript(older_messages)
    if not transcript:
        return conversation.summary

    try:
        llm = llm or get_llm_provider()
        response = llm.generate(
            system=_SUMMARY_SYSTEM_PROMPT,
            messages=[ChatMessage(role="user", content=transcript)],
        )
    except LLMError as exc:
        logger.warning(
            "Conversation summary regeneration failed for conversation %s: %s",
            conversation.id,
            exc,
        )
        return conversation.summary

    conversation.summary = response.text
    conversation.summary_message_count = older_count
    db.commit()
    db.refresh(conversation)
    logger.info(
        "Regenerated summary for conversation %s (covering %d messages)",
        conversation.id,
        older_count,
    )
    return conversation.summary
