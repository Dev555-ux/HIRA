"""Unit tests for app/ai/planning.py (Sprint 58) — pure, deterministic
readiness checking, no LLM/DB/network involved."""

from app.ai.planning import plan_action, plan_actions


def test_booking_missing_date():
    plan = plan_action("Book a meeting with John at 3pm.")
    assert plan.ready is False
    assert plan.missing_field == "date"


def test_booking_missing_time():
    plan = plan_action("Book a meeting with John tomorrow.")
    assert plan.ready is False
    assert plan.missing_field == "time"


def test_booking_missing_both_reports_the_first_required_field():
    plan = plan_action("Book a meeting.")
    assert plan.ready is False
    assert plan.missing_field == "date"


def test_booking_with_complete_details_is_ready():
    plan = plan_action("Book a meeting with John tomorrow at 3 PM.")
    assert plan.ready is True
    assert plan.missing_field is None
    assert plan.clarification_hint is None
    # Sprint 59: app/ai/governance.py keys its policy lookup off this field
    # rather than re-detecting the action itself — this is the contract
    # that keeps the two modules from duplicating keyword logic.
    assert plan.action == "calendar_booking"


def test_reschedule_missing_time():
    plan = plan_action("Reschedule my appointment to tomorrow.")
    assert plan.ready is False
    assert plan.missing_field == "time"


def test_reschedule_with_complete_details_is_ready():
    plan = plan_action("Reschedule my appointment to tomorrow at 10am.")
    assert plan.ready is True


def test_cancel_missing_which_appointment():
    plan = plan_action("Cancel my appointment.")
    assert plan.ready is False
    assert plan.missing_field == "appointment_reference"


def test_cancel_with_a_date_reference_is_ready():
    plan = plan_action("Cancel my appointment for tomorrow.")
    assert plan.ready is True
    assert plan.action == "calendar_cancel"


def test_lead_missing_customer_name():
    plan = plan_action("Create a lead.")
    assert plan.ready is False
    assert plan.missing_field == "customer_name"


def test_lead_with_a_name_is_ready():
    # Requires: customer name only (per this sprint's Requirements section
    # — phone/email are Optional). See deliverables for why this differs
    # from the illustrative dialogue, which asks for contact info too.
    plan = plan_action("Create a lead for John.")
    assert plan.ready is True
    assert plan.action == "crm_lead"


def test_unsupported_action_passes_through_unmodified():
    # No profile's trigger keywords match this phrasing at all — planning
    # has no readiness rule for it, so it doesn't block Stage 2's decision
    # (Sprint 57's existing behaviour stands unmodified for genuinely new
    # action shapes this module doesn't know about yet).
    plan = plan_action("Update my appointment details.")
    assert plan.ready is True
    assert plan.missing_field is None
    assert plan.action is None


def test_non_action_text_is_always_ready():
    # plan_action() is only ever called by the orchestrator when Stage 2
    # already returned tools; this just confirms it degrades harmlessly if
    # given conversational/capability/knowledge text directly.
    for text in ["Hi", "What can you do?", "What are your business hours?"]:
        assert plan_action(text).ready is True


# --- Sprint 75 (DEC-045): per-domain plans -----------------------------------


def test_plan_actions_evaluates_each_requested_domain_independently():
    text = "Reschedule my appointment to tomorrow at 10am and create a lead for John."

    plans = plan_actions(text, ["calendar", "crm"])

    assert len(plans) == 2
    assert plans[0].ready is True
    assert plans[0].action == "calendar_reschedule"
    assert plans[1].ready is True
    assert plans[1].action == "crm_lead"


def test_plan_actions_reports_readiness_per_domain_not_globally():
    """A complete calendar request alongside an incomplete CRM request must
    report each domain's own readiness — one domain being incomplete must
    not be masked by (or mask) the other's."""
    text = "Reschedule my appointment to tomorrow at 10am and create a lead."  # no name

    plans = plan_actions(text, ["calendar", "crm"])

    assert plans[0].ready is True
    assert plans[1].ready is False
    assert plans[1].missing_field == "customer_name"


def test_plan_actions_matches_plan_action_for_a_single_domain():
    """plan_actions() with one domain must agree exactly with plan_action()
    on the same text — same underlying matching logic, just filtered."""
    text = "Book a meeting with John tomorrow at 3 PM."

    assert plan_actions(text, ["calendar"])[0] == plan_action(text)


def test_plan_actions_returns_pass_through_for_a_domain_with_no_matching_profile():
    # "calendar" matches Stage 2 via e.g. "calendar" keyword itself, but no
    # ActionProfile's trigger keywords match this particular phrasing.
    plans = plan_actions("Update my calendar details.", ["calendar"])
    assert plans[0].ready is True
    assert plans[0].action is None


def test_plan_actions_preserves_requested_order():
    text = "Create a lead for John and reschedule my appointment to tomorrow at 10am."

    plans = plan_actions(text, ["crm", "calendar"])

    assert [p.action for p in plans] == ["crm_lead", "calendar_reschedule"]
