"""Conversation orchestrator — the AI engine entry point.

Given an inbound customer message, it: retrieves relevant knowledge, assembles
conversation context (history + injected knowledge), and asks the LLM provider
for a grounded reply — now including the calendar tool schemas (DEC-032), so
the model can propose a booking/reschedule/cancel action instead of only
generating text. Providers (LLM + embeddings) are injected, so this logic is
independent of any vendor and fully testable with mocks.

check_availability is read-only, so it's handled entirely inside this
function: if the model calls it, the result is executed immediately and fed
back as extra system-prompt grounding (reusing the same "inject context into
the system prompt" pattern KB retrieval already uses) for exactly one
follow-up call — bounded by construction, not a loop, so there's no runaway
risk. A write tool (book/reschedule/cancel), if proposed, is returned as-is on
LLMResponse.tool_calls for the caller (app/ai/processing.py,
app/services/replies.py) to turn into a pending approval or execute, per mode.
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
from app.ai.tools import CHECK_AVAILABILITY, TOOL_SCHEMAS, execute_check_availability
from app.models import Business, Conversation, Message

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

    Does not persist or send, and never writes to a calendar — the caller
    decides (e.g. store as pending for Assisted Mode, then send/execute via
    the messaging/calendar services).
    """
    llm = llm or get_llm_provider()
    business = db.get(Business, conversation.business_id)
    retrieved = retrieve_context(
        db, conversation.business_id, user_text, provider=embedding, k=RETRIEVAL_K
    )
    history = _load_history(db, conversation.id)
    system = build_system_prompt(retrieved, business=business)
    messages = build_messages(history, user_text)

    logger.info(
        "Generating reply: business=%s conversation=%s retrieved=%d prompt=%s",
        conversation.business_id,
        conversation.id,
        len(retrieved),
        SYSTEM_PROMPT_VERSION,
    )
    response = llm.generate(system=system, messages=messages, tools=TOOL_SCHEMAS)

    if response.tool_calls and response.tool_calls[0].name == CHECK_AVAILABILITY:
        availability_note = execute_check_availability(
            db, conversation.business_id, response.tool_calls[0]
        )
        system_with_availability = build_system_prompt(
            retrieved, business=business, availability_note=availability_note
        )
        response = llm.generate(
            system=system_with_availability, messages=messages, tools=TOOL_SCHEMAS
        )
        # Deliberately not looped further: if the model calls check_availability
        # again here, that's returned as-is for the caller, same as any other
        # tool call — no risk of runaway recursion.

    return response, retrieved
