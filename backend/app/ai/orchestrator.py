"""Conversation orchestrator — the AI engine entry point.

Given an inbound customer message, it: retrieves relevant knowledge, assembles
conversation context (history + injected knowledge), and asks the LLM provider
for a grounded reply. Providers (LLM + embeddings) are injected, so this logic
is independent of any vendor and fully testable with mocks.

Scope for Milestone 1: the grounded FAQ-answer path. Intent classification,
tool use (booking), and the Assisted-Mode approval gate are layered on later.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.knowledge_base import retrieve_context
from app.ai.llm import LLMProvider, LLMResponse, get_llm_provider
from app.ai.prompts import SYSTEM_PROMPT_VERSION, build_messages, build_system_prompt
from app.models import Conversation, Message

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
RETRIEVAL_K = 5


def _load_history(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return list(reversed(rows))  # oldest-first for the prompt


def generate_reply(
    db: Session,
    conversation: Conversation,
    user_text: str,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
) -> tuple[LLMResponse, list]:
    """Produce a grounded reply. Returns (response, retrieved_entries).

    Does not persist or send — the caller decides (e.g. store as pending for
    Assisted Mode, then send via the messaging service).
    """
    llm = llm or get_llm_provider()
    retrieved = retrieve_context(
        db, conversation.business_id, user_text, provider=embedding, k=RETRIEVAL_K
    )
    history = _load_history(db, conversation.id)
    system = build_system_prompt(retrieved)
    messages = build_messages(history, user_text)

    logger.info(
        "Generating reply: business=%s conversation=%s retrieved=%d prompt=%s",
        conversation.business_id,
        conversation.id,
        len(retrieved),
        SYSTEM_PROMPT_VERSION,
    )
    response = llm.generate(system=system, messages=messages)
    return response, retrieved
