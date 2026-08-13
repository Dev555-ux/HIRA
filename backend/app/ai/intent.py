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

Sprint 75 (DEC-045): tools_for_action()/tools_for_message() above are
unchanged — still "first matching category only," the single-domain path
every existing caller (and test) relies on. domains_for_action()/
tool_schemas_for_domain() below are additive: they let app/ai/plan.py build
a multi-domain execution plan without this module's own single-match
behaviour changing at all.

Sprint 80 (multi-turn intent continuity — production bug): classify_conversation()
now returns `ConversationCategory | None`. `None` means "no rule matched at
all" — a message with no signal of its own (a bare "yes", "sure, go ahead",
or, it turns out, a natural request like "I'd like a teeth cleaning tomorrow
around 3 PM", which matches none of the imperative/first-person-modal
patterns below despite being an unambiguous booking request). Previously
this fell back to CONVERSATION indistinguishably from a confident greeting
or small-talk match, silently discarding the fact that the message was
genuinely ambiguous rather than confidently non-action — which is exactly
what let a live production conversation go tools-less on both the original
request *and* its own follow-up confirmation (see DEC-049). A caller with no
conversation context to offer (evaluation.py's benchmark comparisons, or
this module's own tools_for_message() below) coalesces None to CONVERSATION
itself, preserving every existing behaviour byte-for-byte. A caller *with*
context (app/ai/plan.py::build_execution_plan(), via
app/services/execution_traces.py::get_pending_domain()) instead treats None
as "check whether a workflow is already pending before defaulting to
conversation" — see plan.py for the actual resolution logic; nothing in this
module knows about conversations, history, or the database.

domains_for_action() also gained one additive fallback for the same root
cause found on the Stage 2 side: a message with a time marker (already-
existing `_TIME_MARKER_RE`, not a new pattern) that matches no domain's own
vocabulary still defaults to "calendar" — the general, structural inference
that "the customer named a specific time" is itself calendar-shaped,
independent of whether they used a generic scheduling word like "book" or
named a business-specific service ("teeth cleaning") no fixed keyword list
could ever fully enumerate.
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
    r"(schedule|book|create|remember|learn|answer|help|assist|manage|track|log|handle|update)"
)
# "Can/could YOU <verb>" — asking what HIRA itself is able to do.
_CAPABILITY_MODAL_RE = re.compile(rf"\b(can|could)\s+you\b.*\b{_CAPABILITY_VERBS}\b")
_CAPABILITY_EXPLICIT_RE = re.compile(r"\b(what can you do|what do you do|how do you work)\b")
# Sprint 82 (production bug fix, DEC-058): "Can/could you <verb>" is
# structurally identical whether it's a capability question ("Can you
# schedule appointments?") or an actual request phrased politely ("Can you
# schedule a meeting?", "Can you log me as a lead?") — English marks the
# difference in the object, not the verb: a bare plural with no determiner
# ("appointments", "leads", "CRM records") reads as "in general," while a
# singular instance (bare, "a/an/this/that/the X", or a first/second-person
# target like "me") names something to actually act on now. Reuses
# _ACTION_OBJECT_RE's noun list rather than inventing a new one.
_CONCRETE_REQUEST_RE = re.compile(
    r"\bme\b|\b(a|an|this|that|the)\s+(lead|appointment|meeting|booking|slot|order|invoice)\b"
)

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

# Sprint 81 (production bug fix, DEC-057): a message that volunteers new,
# unprompted information ("My name is Devansh, just so you know.") rather
# than answering or continuing whatever HIRA's own last turn left open.
# Consulted only by app/ai/plan.py::build_execution_plan(), and only in the
# one branch where neither this message's own Stage 1 classification nor its
# own Stage 2 domain match found anything and the sole reason a domain is
# still in play is continuity from a prior turn (`pending_domain`) — a
# generic confirmation ("yes", "go ahead", "sounds good") must still pass
# through this check untouched (see plan.py's docstring for why content-based
# gating there would wrongly block those too), so this only ever screens out
# a message that's actually introducing something new, not merely short or
# ambiguous.
_UNRELATED_DISCLOSURE_RE = re.compile(
    r"^(my name is|my name's|this is)\b|"
    r"\b(by the way|just so you know|just letting you know|fyi)\b",
    re.IGNORECASE,
)


def is_unrelated_disclosure(text: str) -> bool:
    """True for a message that announces new, unprompted information (a
    self-introduction, an aside) rather than continuing a pending workflow —
    see `_UNRELATED_DISCLOSURE_RE` above for exactly what this recognizes and
    why it's scoped this narrowly."""
    return bool(_UNRELATED_DISCLOSURE_RE.search(text.strip()))

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


def classify_conversation(text: str) -> ConversationCategory | None:
    """Stage 1 — deterministic, rule-based, no LLM/network call.

    Checked in order of consequence, not alphabetically: ACTION first (a
    false negative here silently strips tools from a genuine request),
    then CAPABILITY, then KNOWLEDGE.

    Returns None (Sprint 80) when no rule matches at all — genuinely
    ambiguous, not confidently anything. An empty message and an explicit
    greeting/small-talk match are NOT ambiguous — both stay confident
    CONVERSATION returns, same as always. See this module's docstring for
    why the distinction matters and who's responsible for resolving it.
    """
    lower = text.strip().lower()
    if not lower:
        return ConversationCategory.CONVERSATION

    has_time_or_object = bool(
        _TIME_MARKER_RE.search(lower)
        or _ACTION_OBJECT_RE.search(lower)
        or _CONCRETE_REQUEST_RE.search(lower)
    )
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

    return None


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


def domains_for_action(text: str) -> list[str]:
    """Sprint 75 (DEC-045): like tools_for_action, but returns *every*
    matching category's name instead of stopping at the first — ordered by
    where each category's earliest matching keyword first appears in the
    text, so "reschedule my appointment and log me as a lead" plans
    Scheduler before Sales, matching how a human reads the request
    left-to-right. A category with no match contributes nothing; a message
    matching only one category returns a single-item list, identical in
    effect to tools_for_action for that message (Sprint 75 acceptance
    criterion 9 — single-domain behaviour unchanged).

    Planning only — this never calls a tool or exposes anything to the
    model by itself. app/ai/plan.py is what turns this into tool schemas.

    Sprint 80: if no domain's own keywords match at all but the text names
    a specific time (`_TIME_MARKER_RE` — already defined above, not a new
    pattern), defaults to ["calendar"] — "I'd like a teeth cleaning
    tomorrow around 3 PM" names a business-specific service no fixed
    keyword list could enumerate, but a named time is itself a structural,
    generalizable signal that this is calendar-shaped. Only a fallback for
    the *no-match* case — never overrides an actual keyword match (CRM or
    otherwise), so existing multi-domain detection is unchanged.
    """
    lower = text.lower()
    matches: list[tuple[int, str]] = []
    for category in _ACTION_CATEGORIES:
        positions = [lower.find(kw) for kw in category.keywords if kw in lower]
        if positions:
            matches.append((min(positions), category.name))
    matches.sort(key=lambda m: m[0])
    if not matches and _TIME_MARKER_RE.search(lower):
        return ["calendar"]
    return [name for _, name in matches]


def tool_schemas_for_domain(name: str) -> list[ToolSchema]:
    """The tool schemas for one Stage 2 category by name — same list objects
    _ACTION_CATEGORIES already holds, not a copy. Returns [] for an unknown
    name rather than raising: app/ai/plan.py only ever calls this with a
    name domains_for_action() itself just produced, but staying total (not
    partial) avoids a KeyError-shaped failure mode for no real benefit."""
    for category in _ACTION_CATEGORIES:
        if category.name == name:
            return category.tool_schemas
    return []


def tools_for_action(text: str) -> list[ToolSchema]:
    """Stage 2 — only meaningful when classify_conversation() returned
    ACTION. Returns the first _ACTION_CATEGORIES group whose keywords match.

    Returns [] when no known category matches (e.g. "Send an invoice" —
    there is no Payments category yet). This is a deliberate safe fallback:
    an unrecognised action degrades to a plain-text reply rather than
    guessing a tool category. See tools_for_message's module-level note.
    """
    domains = domains_for_action(text)
    return tool_schemas_for_domain(domains[0]) if domains else []


def tools_for_message(text: str) -> tuple[ConversationCategory, list[ToolSchema]]:
    """Single entry point for app/ai/orchestrator.py: runs Stage 1, then
    Stage 2 only if warranted. Returns (category, tool_schemas) — an empty
    list for every category except a recognised Action, never a partial or
    "everything" fallback regardless of confidence (the safest degrade,
    for a request that turns out to need a tool category HIRA doesn't have
    a mapping for yet, is a plain-text answer, not exposing unrelated
    tools).

    No conversation context available here, so an ambiguous (None) Stage 1
    result coalesces to CONVERSATION — identical to this function's
    behaviour before Sprint 80. app/ai/plan.py::build_execution_plan() is
    the context-aware entry point real conversations actually go through.
    """
    category = classify_conversation(text) or ConversationCategory.CONVERSATION
    if category != ConversationCategory.ACTION:
        return category, []

    tools = tools_for_action(text)
    if not tools:
        logger.info("Action classified but no known tool category matched: %r", text)
    return category, tools
