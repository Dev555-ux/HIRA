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

Demo Mode (Sprint 55): this is also the earliest point that knows whether
the business has any Business Knowledge at all (context.has_knowledge, from
app/ai/context.py). A business with none gets a different system prompt
(app/ai/prompts.py::build_demo_system_prompt) and no tool schemas — there's
no real KB to ground answers in yet, and no real calendar/CRM data to check
tools against, so offering them only invited the model to misfire (e.g.
proposing check_availability on a bare "Hi"). Every caller of generate_reply
— this Demo Chat, real WhatsApp inbound, and Assisted Mode's regenerate —
gets this the same way, since a business with zero Business Knowledge
behaves identically confusing for a real customer as it does in Demo Chat.
Once Business Knowledge exists, this branch is never taken and nothing here
changes from before.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.context import RETRIEVAL_K, build_context
from app.ai.embeddings import EmbeddingProvider
from app.ai.llm import LLMProvider, LLMResponse, get_llm_provider
from app.ai.prompts import (
    DEMO_SYSTEM_PROMPT_VERSION,
    SYSTEM_PROMPT_VERSION,
    build_demo_system_prompt,
    build_messages,
    build_system_prompt,
)
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

    if not context.has_knowledge:
        logger.info(
            "Generating reply: business=%s conversation=%s prompt=%s (no Business Knowledge yet)",
            conversation.business_id,
            conversation.id,
            DEMO_SYSTEM_PROMPT_VERSION,
        )
        demo_system = build_demo_system_prompt(context)
        messages = build_messages(context.history, user_text)
        response = llm.generate(system=demo_system, messages=messages)
        return response, context.retrieved_kb

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
