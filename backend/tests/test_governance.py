"""Unit tests for app/ai/governance.py (Sprint 59) — pure policy lookup,
no LLM/DB/network involved."""

from app.ai.governance import ExecutionDecision, evaluate_execution


def test_calendar_booking_executes_now():
    result = evaluate_execution("calendar_booking")
    assert result.decision == ExecutionDecision.EXECUTE_NOW


def test_calendar_cancellation_requires_confirmation():
    result = evaluate_execution("calendar_cancel")
    assert result.decision == ExecutionDecision.REQUIRES_CONFIRMATION
    assert result.confirmation_prompt is not None
    assert "cancel" in result.confirmation_prompt.lower()


def test_calendar_reschedule_requires_confirmation():
    result = evaluate_execution("calendar_reschedule")
    assert result.decision == ExecutionDecision.REQUIRES_CONFIRMATION
    assert result.confirmation_prompt is not None


def test_crm_create_executes_now():
    result = evaluate_execution("crm_lead")
    assert result.decision == ExecutionDecision.EXECUTE_NOW


def test_crm_delete_requires_confirmation():
    result = evaluate_execution("crm_lead_delete")
    assert result.decision == ExecutionDecision.REQUIRES_CONFIRMATION
    assert result.confirmation_prompt is not None


def test_approval_action_refund_requires_human_approval():
    result = evaluate_execution("refund")
    assert result.decision == ExecutionDecision.REQUIRES_HUMAN_APPROVAL
    assert result.approval_reason is not None


def test_approval_action_delete_customer_requires_human_approval():
    result = evaluate_execution("delete_customer")
    assert result.decision == ExecutionDecision.REQUIRES_HUMAN_APPROVAL
    assert result.approval_reason is not None


def test_approval_action_payment_requires_human_approval():
    result = evaluate_execution("payment")
    assert result.decision == ExecutionDecision.REQUIRES_HUMAN_APPROVAL


def test_confirmation_action_invoice_send_requires_confirmation():
    result = evaluate_execution("invoice_send")
    assert result.decision == ExecutionDecision.REQUIRES_CONFIRMATION


def test_unknown_action_is_blocked_with_a_helpful_explanation():
    result = evaluate_execution("some_future_capability_no_one_has_built_yet")
    assert result.decision == ExecutionDecision.BLOCKED
    assert result.explanation is not None
    assert "some_future_capability_no_one_has_built_yet" in result.explanation


def test_blocked_action_none_is_blocked_with_a_helpful_explanation():
    result = evaluate_execution(None)
    assert result.decision == ExecutionDecision.BLOCKED
    assert result.explanation is not None


def test_every_policy_result_only_populates_fields_relevant_to_its_decision():
    # Not a hard contract, just a sanity check that the registry data is
    # internally consistent — a BLOCKED/EXECUTE_NOW result carrying a stray
    # confirmation_prompt would be confusing for the orchestrator's fallback
    # chain (confirmation_prompt or approval_reason or explanation).
    for action in ("calendar_booking", "crm_lead"):
        result = evaluate_execution(action)
        assert result.decision == ExecutionDecision.EXECUTE_NOW
        assert result.confirmation_prompt is None
        assert result.approval_reason is None
