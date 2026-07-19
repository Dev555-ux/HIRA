"""Intent routing for tool exposure (Sprint 57).

Two stages, both pure and dependency-free (no LLM call, no network request,
no database access), so they add negligible latency ahead of the real LLM
call in app/ai/orchestrator.py:

Stage 1 (classify_conversation): every user message is classified into one
of CONVERSATION / CAPABILITY / KNOWLEDGE / ACTION before the orchestrator
decides what to send the model. This replaces "always send all tools" with
"only send tools when the message is actually asking HIRA to do something."

Stage 2 (tools_for_action): only meaningful when Stage 1 returned ACTION.
Narrows further to the minimum tool schema group the message's own wording
implies (Calendar, CRM, ...), reusing the schema lists app/ai/tools.py and
app/ai/lead_tools.py already define — no schema is duplicated or redefined
here.

Business Knowledge (RAG) is deliberately NOT a category here. Retrieval
(app/ai/context.py::retrieve_context) and prompt grounding
(app/ai/prompts.py::build_system_prompt) already run unconditionally,
regardless of what these two stages decide — a message classified KNOWLEDGE
just means "don't send action tools," never "skip retrieval." See the
architecture review preceding this sprint for the reasoning.

Extending with a new tool category (Payments, Communication, ...) means
adding one _ActionCategory entry to _ACTION_CATEGORIES below — no branching
logic changes, no other module needs to know a new category exists.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import Enum

from app.ai.llm.base import ToolSchema
from app.ai.tools import CALENDAR_TOOL_SCHEMAS, LEAD_TOOL_SCHEMAS

logger = logging.getLogger(__name__)


class ConversationCategory(str, Enum):
    CONVERSATION = "conversation"
    CAPABILITY = "capability"
    KNOWLEDGE = "knowledge"
    ACTION = "action"


_CAPABILITY_VERBS = (
    r"(schedule|book|create|remember|learn|answer|help|assist|manage|track|log|handle)"
)
# "Can/could YOU <verb>" — asking what HIRA itself is able to do.
_CAPABILITY_MODAL_RE = re.compile(rf"\b(can|could)\s+you\b.*\b{_CAPABILITY_VERBS}\b")
_CAPABILITY_EXPLICIT_RE = re.compile(r"\b(what can you do|what do you do|how do you work)\b")

# Imperative mood at the start of the message ("Book a meeting tomorrow").
_ACTION_VERB_RE = re.compile(
    r"^(book|schedule|cancel|reschedule|create|add|remove|delete|send|update|set)\b"
)
# "Can/could I <verb>" — a first-person request to do something, distinct
# from _CAPABILITY_MODAL_RE's "can YOU" (asking about HIRA's own ability).
_FIRST_PERSON_ACTION_RE = re.compile(
    r"\b(can|could)\s+(i|we)\b.*\b(book|schedule|cancel|reschedule|get)\b"
)
_TIME_MARKER_RE = re.compile(
    r"\b(today|tomorrow|tonight|next\s+\w+|this\s+\w+|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}(:\d{2})?\s?(am|pm)|\d{1,2}/\d{1,2})\b"
)
# A concrete object of an action verb ("my appointment"), as opposed to a
# generic noun ("my business") that a capability question might also use.
_ACTION_OBJECT_RE = re.compile(r"\bmy\s+(appointment|meeting|booking|lead|order|invoice)\b")

_GREETING_RE = re.compile(r"^(hi|hello|hey|yo|good morning|good afternoon|good evening)\b")
_SMALL_TALK_RE = re.compile(r"\b(how are you|tell me about yourself|thank(s| you))\b")

_KNOWLEDGE_KEYWORDS = (
    "hour",
    "hours",
    "open",
    "close",
    "price",
    "pricing",
    "cost",
    "fee",
    "refund",
    "policy",
    "policies",
    "service",
    "services",
    "product",
    "products",
    "location",
    "address",
    "offer",
)
_KNOWLEDGE_QUESTION_RE = re.compile(r"^(what|where|when|how much|do you have)\b")


def classify_conversation(text: str) -> ConversationCategory:
    """Stage 1 — deterministic, rule-based, no LLM/network call.

    Checked in order of consequence, not alphabetically: ACTION first (a
    false negative here silently strips tools from a genuine request),
    then CAPABILITY, then KNOWLEDGE, defaulting to CONVERSATION — the safe
    fallback (see tools_for_message) — when nothing matches.
    """
    lower = text.strip().lower()
    if not lower:
        return ConversationCategory.CONVERSATION

    has_time_or_object = bool(_TIME_MARKER_RE.search(lower) or _ACTION_OBJECT_RE.search(lower))
    is_imperative = bool(_ACTION_VERB_RE.match(lower))
    is_first_person_action = bool(_FIRST_PERSON_ACTION_RE.search(lower))
    is_modal_capability = bool(_CAPABILITY_MODAL_RE.search(lower))

    if is_imperative or is_first_person_action or (is_modal_capability and has_time_or_object):
        return ConversationCategory.ACTION

    if is_modal_capability or _CAPABILITY_EXPLICIT_RE.search(lower):
        return ConversationCategory.CAPABILITY

    if _GREETING_RE.match(lower) or _SMALL_TALK_RE.search(lower):
        return ConversationCategory.CONVERSATION

    if _KNOWLEDGE_QUESTION_RE.match(lower) and any(kw in lower for kw in _KNOWLEDGE_KEYWORDS):
        return ConversationCategory.KNOWLEDGE
    if any(kw in lower for kw in _KNOWLEDGE_KEYWORDS):
        return ConversationCategory.KNOWLEDGE

    return ConversationCategory.CONVERSATION


@dataclass(frozen=True)
class _ActionCategory:
    name: str
    keywords: tuple[str, ...]
    tool_schemas: list[ToolSchema]


# Stage 2 registry — reuses app/ai/tools.py's and app/ai/lead_tools.py's
# existing schema groups verbatim (same list objects, nothing duplicated).
# CRM is checked before Calendar: lead-specific words are the more
# distinctive signal, and the two keyword sets don't otherwise overlap.
# Add a new _ActionCategory here to support a new tool category — no other
# code in this module changes.
_ACTION_CATEGORIES: tuple[_ActionCategory, ...] = (
    _ActionCategory(
        name="crm",
        keywords=("lead", "leads", "crm", "prospect", "follow up", "follow-up"),
        tool_schemas=LEAD_TOOL_SCHEMAS,
    ),
    _ActionCategory(
        name="calendar",
        keywords=(
            "meeting",
            "meetings",
            "appointment",
            "appointments",
            "book",
            "booking",
            "schedule",
            "reschedule",
            "cancel",
            "availability",
            "slot",
            "calendar",
        ),
        tool_schemas=CALENDAR_TOOL_SCHEMAS,
    ),
)


def tools_for_action(text: str) -> list[ToolSchema]:
    """Stage 2 — only meaningful when classify_conversation() returned
    ACTION. Returns the first _ACTION_CATEGORIES group whose keywords match.

    Returns [] when no known category matches (e.g. "Send an invoice" —
    there is no Payments category yet). This is a deliberate safe fallback:
    an unrecognised action degrades to a plain-text reply rather than
    guessing a tool category. See tools_for_message's module-level note.
    """
    lower = text.lower()
    for category in _ACTION_CATEGORIES:
        if any(keyword in lower for keyword in category.keywords):
            return category.tool_schemas
    return []


def tools_for_message(text: str) -> tuple[ConversationCategory, list[ToolSchema]]:
    """Single entry point for app/ai/orchestrator.py: runs Stage 1, then
    Stage 2 only if warranted. Returns (category, tool_schemas) — an empty
    list for every category except a recognised Action, never a partial or
    "everything" fallback regardless of confidence (the safest degrade,
    for a request that turns out to need a tool category HIRA doesn't have
    a mapping for yet, is a plain-text answer, not exposing unrelated
    tools).
    """
    category = classify_conversation(text)
    if category != ConversationCategory.ACTION:
        return category, []

    tools = tools_for_action(text)
    if not tools:
        logger.info("Action classified but no known tool category matched: %r", text)
    return category, tools
