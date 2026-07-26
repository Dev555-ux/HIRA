"""Unit tests for app/ai/plan.py (Sprint 75, DEC-045) — pure, deterministic
plan-building, no LLM/DB/network involved. Every step in a returned plan
must already have cleared governance; this is what proves the "no employee
bypasses governance" acceptance criterion at the planning layer."""

from app.ai.intent import ConversationCategory
from app.ai.lead_tools import CREATE_LEAD
from app.ai.plan import build_execution_plan
from app.ai.roles import SALES_EXECUTIVE, SCHEDULER
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    RESCHEDULE_APPOINTMENT,
)


def test_non_action_message_produces_an_empty_plan():
    plan = build_execution_plan("Hi there!")
    assert plan.category == ConversationCategory.CONVERSATION
    assert plan.steps == ()
    assert plan.tools == []
    assert plan.clarification_hint is None


def test_unrecognised_action_produces_an_empty_plan():
    plan = build_execution_plan("Send an invoice.")
    assert plan.category == ConversationCategory.ACTION
    assert plan.steps == ()


def test_single_domain_message_produces_a_single_step_plan():
    plan = build_execution_plan("Book a meeting with John tomorrow at 3 PM.")

    assert len(plan.steps) == 1
    step = plan.steps[0]
    assert step.domain == "calendar"
    assert step.action == "calendar_booking"
    assert step.role == SCHEDULER
    assert {t.name for t in step.tools} == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }
    assert plan.clarification_hint is None


def test_single_domain_plan_matches_pre_sprint_75_tools_for_message():
    """The exact regression guard for acceptance criterion 9: a single-
    domain plan's tools must be identical to what tools_for_message() alone
    would have offered before this sprint existed."""
    from app.ai.intent import tools_for_message

    text = "Book a meeting with John tomorrow at 3 PM."
    _, expected_tools = tools_for_message(text)

    plan = build_execution_plan(text)

    assert {t.name for t in plan.tools} == {t.name for t in expected_tools}


def test_two_domain_message_produces_an_ordered_two_step_plan():
    # Both calendar_booking and crm_lead are EXECUTE_NOW policies
    # (app/ai/governance.py) — the happy path where neither domain is
    # withheld. (calendar_reschedule/cancel deliberately require
    # confirmation — see the governance test below, which covers that.)
    text = "Book a meeting tomorrow at 10am and create a lead for John."

    plan = build_execution_plan(text)

    assert len(plan.steps) == 2
    assert plan.steps[0].domain == "calendar"
    assert plan.steps[0].action == "calendar_booking"
    assert plan.steps[0].role == SCHEDULER
    assert plan.steps[1].domain == "crm"
    assert plan.steps[1].action == "crm_lead"
    assert plan.steps[1].role == SALES_EXECUTIVE
    assert plan.clarification_hint is None
    # The union of both steps' tools, in step order — calendar's tools all
    # precede crm's (each step contributes its whole tool block, not
    # individually interleaved).
    calendar_names = {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }
    tool_names = [t.name for t in plan.tools]
    assert tool_names[:4] and set(tool_names[:4]) == calendar_names
    assert CREATE_LEAD in tool_names[4:]


def test_plan_stops_before_an_unready_domain_and_omits_its_tools():
    """Objective D's "stopping conditions": the first domain is complete and
    ready, the second is missing a required field — the plan must include
    only the first, with a hint describing the second's gap, not silently
    drop the requirement or offer the second domain's tools anyway."""
    text = "Book a meeting tomorrow at 10am and create a lead."  # no name for the lead

    plan = build_execution_plan(text)

    assert len(plan.steps) == 1
    assert plan.steps[0].domain == "calendar"
    assert plan.clarification_hint is not None
    assert "name" in plan.clarification_hint
    assert CREATE_LEAD not in {t.name for t in plan.tools}


def test_plan_stops_before_a_second_domain_that_requires_confirmation():
    """The reschedule-requires-confirmation case, isolated: governance is
    evaluated per step even when an earlier step is fine — a ready,
    EXECUTE_NOW first domain does not entitle a later, policy-gated domain
    to skip its own check."""
    text = "Create a lead for John and reschedule my appointment to tomorrow at 10am."

    plan = build_execution_plan(text)

    assert len(plan.steps) == 1
    assert plan.steps[0].domain == "crm"
    assert plan.clarification_hint is not None
    assert BOOK_APPOINTMENT not in {t.name for t in plan.tools}
    assert RESCHEDULE_APPOINTMENT not in {t.name for t in plan.tools}


def test_plan_stops_before_a_domain_that_requires_confirmation():
    """Governance, not bypassed: calendar_cancel requires confirmation
    (app/ai/governance.py) — even though a second domain (crm) is also
    requested and would otherwise be ready, the plan must not include a
    second step "in parallel" with an ungoverned first one."""
    text = "Cancel my appointment for tomorrow and create a lead for John."

    plan = build_execution_plan(text)

    assert len(plan.steps) == 0
    assert plan.clarification_hint is not None
    assert CREATE_LEAD not in {t.name for t in plan.tools}


def test_plan_never_exceeds_the_shared_two_call_cap():
    """Even if intent.py somehow matched more than two domains in the
    future, the plan must stay capped at the same MAX_TOOL_CALLS_PER_TURN
    app/ai/tools.py's execution layer already enforces — one shared
    constant, not two numbers that could drift apart."""
    from app.ai.tools import MAX_TOOL_CALLS_PER_TURN

    assert MAX_TOOL_CALLS_PER_TURN == 2

    text = "Reschedule my appointment to tomorrow at 10am and create a lead for John."
    plan = build_execution_plan(text)
    assert len(plan.steps) <= MAX_TOOL_CALLS_PER_TURN


def test_domain_with_no_matching_action_profile_is_still_included():
    """A domain Stage 2 matched but Planning has no specific profile for is
    pass-through (ready=True, action=None) — governance.evaluate_execution
    is never called with None (which would BLOCK it); the step is included
    with its full domain tool set, exactly like the pre-Sprint-75 single-
    action pass-through behaviour."""
    plan = build_execution_plan("Update my calendar details.")

    assert len(plan.steps) == 1
    assert plan.steps[0].action is None
    assert plan.steps[0].tools  # still offered, not blocked
