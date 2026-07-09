"""Conversation orchestrator — the AI engine entry point.

Given an inbound customer message, assembles full context via the Context
Builder (app/ai/context.py, DEC-034) and asks the LLM provider for a grounded
reply — including the calendar/CRM tool schemas (DEC-032/DEC-033), so the
model can propose an action instead of only generating text. This module
stays thin by design: context assembly, memory, and prompt construction each
live in their own module; this one just wires them together and handles the
one bounded check_availability round-trip. Providers (LLM + embeddings) are
injected, so this logic is independent of any vendor and fully testable with
mocks.

check_availability is read-only, so it's handled entirely inside this
function: if the model calls it, the result is executed immediately and fed
back as extra system-prompt grounding (reusing the same "inject context into
the system prompt" pattern KB retrieval already uses) for exactly one
follow-up call — bounded by construction, not a loop, so there's no runaway
risk. A write tool (book/reschedule/cancel/CRM), if proposed, is returned
as-is on LLMResponse.tool_calls for the caller (app/ai/processing.py,
app/services/replies.py) to turn into a pending approval or execute, per mode.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.context import RETRIEVAL_K, build_context
from app.ai.embeddings import EmbeddingProvider
from app.ai.llm import LLMProvider, LLMResponse, get_llm_provider
from app.ai.prompts import SYSTEM_PROMPT_VERSION, build_messages, build_system_prompt
from app.ai.tools import CHECK_AVAILABILITY, TOOL_SCHEMAS, execute_check_availability
from app.models import Conversation

logger = logging.getLogger(__name__)


def generate_reply(
    db: Session,
    conversation: Conversation,
    user_text: str,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
) -> tuple[LLMResponse, list]:
    """Produce a grounded reply. Returns (response, retrieved_entries).

    Does not persist or send, and never writes to a calendar/CRM — the caller
    decides (e.g. store as pending for Assisted Mode, then send/execute via
    the messaging/calendar/CRM services).
    """
    llm = llm or get_llm_provider()
    context = build_context(
        db, conversation, user_text, llm=llm, embedding=embedding, k=RETRIEVAL_K
    )
    system = build_system_prompt(context)
    messages = build_messages(context.history, user_text)

    logger.info(
        "Generating reply: business=%s conversation=%s retrieved=%d prompt=%s",
        conversation.business_id,
        conversation.id,
        len(context.retrieved_kb),
        SYSTEM_PROMPT_VERSION,
    )
    response = llm.generate(system=system, messages=messages, tools=TOOL_SCHEMAS)

    if response.tool_calls and response.tool_calls[0].name == CHECK_AVAILABILITY:
        availability_note = execute_check_availability(
            db, conversation.business_id, response.tool_calls[0]
        )
        system_with_availability = build_system_prompt(context, availability_note=availability_note)
        response = llm.generate(
            system=system_with_availability, messages=messages, tools=TOOL_SCHEMAS
        )
        # Deliberately not looped further: if the model calls check_availability
        # again here, that's returned as-is for the caller, same as any other
        # tool call — no risk of runaway recursion.

    return response, context.retrieved_kb
