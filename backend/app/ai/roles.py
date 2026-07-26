"""Employee Registry (Sprint 74, Phase 1 — DEC-043).

A small, data-driven mapping from employee role -> what it owns (which
tools, what to add to the system prompt) and what it's for (description,
capabilities) — not a new agent runtime. Every existing extension seam
(app/ai/tools.py's schema lists, app/ai/prompts.py's system prompt,
app/ai/governance.py's policy table) is reused unchanged; this module only
adds a *label* over them, matching the provider-registry pattern already
established for LLMProvider (app/ai/llm/__init__.py) and CalendarProvider
(app/calendar/providers/__init__.py) — plain data, not a class hierarchy,
since a role here is configuration, not polymorphic behavior.

Adding a new employee: add one AgentRole to AGENT_ROLES below. No
orchestration code changes — app/ai/tools.py's response_to_message_fields()
looks up ownership by tool name via role_for_tool(), never by a hardcoded
if/else chain.

CRM is deliberately not a role here (DEC-043, approved): it is the shared
data/audit substrate every employee reads and writes through (Business,
Customer, Lead, LeadEvent, app/ai/context.py::ConversationContext) — not a
persona with its own prompt or tools. Building it as a sixth voice would
mean two "employees" (CRM and Sales Executive) fighting over identical
write access to the same Lead row with no schema-level way to tell them
apart (see DEC-043 §0.3).

Customer Success is deliberately not a role here either (Sprint 74 Phase 1
non-goal) — it is fundamentally a proactive/scheduled function (no inbound
customer message triggers it), which needs a background-worker mechanism
this phase explicitly does not build. It stays out of AGENT_ROLES entirely
rather than being registered inert, since (unlike Bookkeeper) it has no
synchronous, turn-triggered behavior at all to register.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.lead_tools import CREATE_LEAD, SET_LEAD_FOLLOW_UP, UPDATE_LEAD_STAGE
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    RESCHEDULE_APPOINTMENT,
)

RECEPTIONIST = "receptionist"
SCHEDULER = "scheduler"
SALES_EXECUTIVE = "sales_executive"
BOOKKEEPER = "bookkeeper"


@dataclass(frozen=True)
class AgentRole:
    key: str
    display_name: str
    description: str
    # Folded into the system prompt when this role's tools are in play
    # (app/ai/prompts.py) — "" for a role with nothing role-specific to add
    # beyond what the base prompt/tool descriptions already say.
    prompt_addition: str
    tool_names: tuple[str, ...]
    # Human-readable, not machine-enforced — documentation for the founder
    # (Settings, Founder Ops reporting) and for future employees' own
    # capability lists, not a permissions system.
    capabilities: tuple[str, ...]


AGENT_ROLES: dict[str, AgentRole] = {
    role.key: role
    for role in (
        AgentRole(
            key=RECEPTIONIST,
            display_name="Receptionist",
            description=(
                "The default, always-on employee — first contact for every conversation. "
                "Answers questions grounded in this business's Knowledge Base and triages "
                "requests toward the right specialist tools."
            ),
            prompt_addition="",
            tool_names=(),
            capabilities=(
                "Answer customer questions grounded in Business Knowledge",
                "Triage requests toward booking or lead-logging tools when warranted",
            ),
        ),
        AgentRole(
            key=SCHEDULER,
            display_name="Scheduler",
            description="Owns calendar actions — checking availability and booking/changing appointments.",
            prompt_addition="",
            tool_names=(
                CHECK_AVAILABILITY,
                BOOK_APPOINTMENT,
                RESCHEDULE_APPOINTMENT,
                CANCEL_APPOINTMENT,
            ),
            capabilities=(
                "Check calendar availability",
                "Book a new appointment",
                "Reschedule or cancel an existing appointment",
            ),
        ),
        AgentRole(
            key=SALES_EXECUTIVE,
            display_name="Sales Executive",
            description="Owns the customer's pipeline — logging leads and advancing them.",
            prompt_addition="",
            tool_names=(CREATE_LEAD, UPDATE_LEAD_STAGE, SET_LEAD_FOLLOW_UP),
            capabilities=(
                "Log a new lead",
                "Advance a lead's pipeline stage",
                "Schedule a follow-up",
            ),
        ),
        AgentRole(
            key=BOOKKEEPER,
            display_name="Bookkeeper",
            description=(
                "Reserved for future financial/bookkeeping actions. No tools exist yet — "
                "registered here to prove the registry supports an employee with no "
                "capabilities today, ready to gain them without any orchestration change. "
                "app/ai/governance.py already forward-declares policies for the actions "
                "this role will eventually own (invoice_send, refund, payment) — see its "
                "module docstring. Explicitly out of scope for Sprint 74 Phase 1 (no "
                "billing/pricing/payments work), per that sprint's own non-goals."
            ),
            prompt_addition="",
            tool_names=(),
            capabilities=(),
        ),
    )
}

# Built once at import time: tool name -> owning role key. A tool owned by
# no role (shouldn't happen for any real tool in TOOL_SCHEMAS, but kept
# total rather than partial) resolves to None at the call site instead of
# raising — an unattributed action is a labeling gap, not a reason to fail
# the turn.
_TOOL_OWNER: dict[str, str] = {
    tool_name: role.key for role in AGENT_ROLES.values() for tool_name in role.tool_names
}


def role_for_tool(tool_name: str) -> str | None:
    """The employee that owns a given tool name, or None if unattributed."""
    return _TOOL_OWNER.get(tool_name)
