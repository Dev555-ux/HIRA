"""Tests for the Employee Registry (app/ai/roles.py) — Sprint 74 Phase 1, DEC-043."""

from app.ai.lead_tools import CREATE_LEAD, SET_LEAD_FOLLOW_UP, UPDATE_LEAD_STAGE
from app.ai.roles import (
    AGENT_ROLES,
    BOOKKEEPER,
    RECEPTIONIST,
    SALES_EXECUTIVE,
    SCHEDULER,
    role_for_tool,
)
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    RESCHEDULE_APPOINTMENT,
)


def test_registry_defines_exactly_the_four_phase_1_employees():
    assert set(AGENT_ROLES.keys()) == {RECEPTIONIST, SCHEDULER, SALES_EXECUTIVE, BOOKKEEPER}


def test_crm_is_not_a_registered_employee():
    """DEC-043, approved: CRM is the shared substrate every employee reads/
    writes through, not a persona — it must never appear as a registry key."""
    assert "crm" not in AGENT_ROLES


def test_customer_success_is_not_a_registered_employee():
    """Sprint 74 Phase 1 non-goal — no proactive/background capability exists
    to register a role for yet."""
    assert "customer_success" not in AGENT_ROLES


def test_scheduler_owns_exactly_the_calendar_tools():
    assert set(AGENT_ROLES[SCHEDULER].tool_names) == {
        CHECK_AVAILABILITY,
        BOOK_APPOINTMENT,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }


def test_sales_executive_owns_exactly_the_lead_tools():
    assert set(AGENT_ROLES[SALES_EXECUTIVE].tool_names) == {
        CREATE_LEAD,
        UPDATE_LEAD_STAGE,
        SET_LEAD_FOLLOW_UP,
    }


def test_receptionist_owns_no_tools():
    """The Receptionist is the default persona (general Q&A/triage) — it has
    nothing to attribute a tool call to, by design."""
    assert AGENT_ROLES[RECEPTIONIST].tool_names == ()


def test_bookkeeper_is_registered_with_no_tools_yet():
    """Proves the registry supports an employee with zero capabilities today
    (extensibility), without violating Sprint 74's no-billing/payments
    non-goal — see the role's own description."""
    bookkeeper = AGENT_ROLES[BOOKKEEPER]
    assert bookkeeper.tool_names == ()
    assert bookkeeper.display_name == "Bookkeeper"


def test_every_role_has_a_non_empty_description():
    for role in AGENT_ROLES.values():
        assert role.description.strip()


def test_role_for_tool_resolves_calendar_tools_to_scheduler():
    assert role_for_tool(BOOK_APPOINTMENT) == SCHEDULER
    assert role_for_tool(CHECK_AVAILABILITY) == SCHEDULER
    assert role_for_tool(RESCHEDULE_APPOINTMENT) == SCHEDULER
    assert role_for_tool(CANCEL_APPOINTMENT) == SCHEDULER


def test_role_for_tool_resolves_lead_tools_to_sales_executive():
    assert role_for_tool(CREATE_LEAD) == SALES_EXECUTIVE
    assert role_for_tool(UPDATE_LEAD_STAGE) == SALES_EXECUTIVE
    assert role_for_tool(SET_LEAD_FOLLOW_UP) == SALES_EXECUTIVE


def test_role_for_tool_returns_none_for_an_unknown_tool():
    assert role_for_tool("send_invoice") is None


def test_no_tool_is_owned_by_more_than_one_role():
    """A real, structural overlap check — not just a naming-convention
    assumption. If this ever fails, two employees would silently fight over
    attribution for the same tool call."""
    seen: dict[str, str] = {}
    for role in AGENT_ROLES.values():
        for tool_name in role.tool_names:
            assert tool_name not in seen, (
                f"{tool_name!r} is owned by both {seen.get(tool_name)!r} and {role.key!r}"
            )
            seen[tool_name] = role.key
