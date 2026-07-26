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

Tool routing (Sprint 57): once Business Knowledge exists, tool schemas are
no longer sent unconditionally on every turn. app/ai/intent.py's
tools_for_message() classifies the message first (Conversation/Capability/
Knowledge/Action) and only returns real tool schemas for Action — narrowed
further to the relevant category (Calendar/CRM/...). A capability question
like "Can you schedule meetings?" or an off-topic knowledge question no
longer offers the model a tool it has no reason to call, which is what let
Groq's malformed-tool-call 400 (app/ai/llm/groq.py) surface as a generic
fallback for ordinary conversational turns. Business Knowledge grounding
itself (retrieve_context/build_system_prompt) is untouched by this — it's
not a tool category, it's already unconditional context assembly.

Action planning (Sprint 58): once Stage 2 has picked a real tool category
(tools is non-empty), app/ai/planning.py::plan_action() checks whether the
message actually has enough detail to act on — a bare "Book a meeting."
has no date or time, so nothing gets booked blind. An incomplete request
gets tools=[] for this turn, same as any other no-tools case, plus a short
hint folded into the system prompt (app/ai/prompts.py) so the model asks
one natural follow-up question instead of guessing or silently failing.
This never changes *which* category Stage 2 picked, only whether those
tools are handed to the model on this particular turn.

Execution governance (Sprint 59): once a request is ready (plan.ready and
plan.action is a known name, e.g. "calendar_booking"), app/ai/governance.py
::evaluate_execution() decides *whether* it may run automatically — some
actions (booking, logging a lead) are routine and proceed; others
(cancelling, rescheduling) are policy-gated to require the customer's
confirmation first, using the exact same tools=[]/clarification_hint
mechanism as an incomplete request — the model asks a confirming question
in its own words instead of the tool being offered outright. This is a
policy decision, not a readiness check: it never runs for a request Sprint
58 already withheld, and it never changes which action Sprint 57/58 picked
— only whether it's allowed through unmoderated this turn. A request with
no named action (Sprint 58 found no matching profile) skips governance
entirely and keeps Sprint 57/58's existing pass-through behaviour.

Cross-employee planning (Sprint 75, DEC-045): the three paragraphs above
still describe exactly what happens conceptually, but the *code* moved —
app/ai/plan.py::build_execution_plan() now runs Stage 1/2 classification,
per-domain readiness, and per-domain governance itself, generalized from
"one domain" to "up to app/ai/tools.py::MAX_TOOL_CALLS_PER_TURN domains,
each independently gated the same way." This function just calls it once
and uses the resulting ExecutionPlan.tools/clarification_hint — it no
longer owns any of that gating logic directly. A single-domain message
still produces a single-step plan and therefore identical behaviour to
before this sprint.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ai.context import RETRIEVAL_K, build_context
from app.ai.embeddings import EmbeddingProvider
from app.ai.intent import classify_conversation
from app.ai.llm import LLMProvider, LLMResponse, get_llm_provider
from app.ai.plan import ExecutionPlan, build_execution_plan
from app.ai.prompts import (
    DEMO_SYSTEM_PROMPT_VERSION,
    SYSTEM_PROMPT_VERSION,
    build_demo_system_prompt,
    build_messages,
    build_system_prompt,
)
from app.ai.tools import CHECK_AVAILABILITY, execute_check_availability
from app.models import Conversation

logger = logging.getLogger(__name__)


def generate_reply(
    db: Session,
    conversation: Conversation,
    user_text: str,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
) -> tuple[LLMResponse, list, ExecutionPlan]:
    """Produce a grounded reply. Returns (response, retrieved_entries, plan).

    `plan` (Sprint 76) is the ExecutionPlan actually used to decide which
    tools, if any, were offered this turn — callers use it for execution
    tracing (app/services/execution_traces.py) rather than recomputing
    build_execution_plan() themselves, which would silently lie about a Demo
    Mode turn (no Business Knowledge yet) that never runs planning at all
    below. In that branch, `plan` still reflects Stage 1 classification
    (so a trace can tell "this looked like an action" apart from "this was
    small talk") but always has empty steps, since no tools were offered.

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
        demo_plan = ExecutionPlan(category=classify_conversation(user_text), steps=())
        return response, context.retrieved_kb, demo_plan

    messages = build_messages(context.history, user_text)

    # Sprint 75 (DEC-045): Stage 1/2 classification, per-domain readiness,
    # and per-domain governance all now live behind this one call
    # (app/ai/plan.py) instead of inline here — an ExecutionPlan already
    # reflects every gate a single action used to go through, generalized
    # to up to MAX_TOOL_CALLS_PER_TURN domains. A message matching only one
    # domain produces an identical-shape single-step plan, so this is a
    # pure refactor for single-domain requests, not a behaviour change.
    plan = build_execution_plan(user_text)
    tools = plan.tools

    system = build_system_prompt(context, clarification_hint=plan.clarification_hint)
    logger.info(
        "Generating reply: business=%s conversation=%s retrieved=%d category=%s tools=%d "
        "steps=%s ready=%s prompt=%s",
        conversation.business_id,
        conversation.id,
        len(context.retrieved_kb),
        plan.category.value,
        len(tools),
        [step.role for step in plan.steps],
        plan.clarification_hint is None,
        SYSTEM_PROMPT_VERSION,
    )
    response = llm.generate(system=system, messages=messages, tools=tools)

    if response.tool_calls and response.tool_calls[0].name == CHECK_AVAILABILITY:
        availability_note = execute_check_availability(
            db, conversation.business_id, response.tool_calls[0]
        )
        system_with_availability = build_system_prompt(context, availability_note=availability_note)
        response = llm.generate(system=system_with_availability, messages=messages, tools=tools)
        # Deliberately not looped further: if the model calls check_availability
        # again here, that's returned as-is for the caller, same as any other
        # tool call — no risk of runaway recursion.

    return response, context.retrieved_kb, plan
