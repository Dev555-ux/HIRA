"""Tests for app/ai/evaluation.py — the plan comparison framework (Sprint 76,
Objective D). Doubles as the regression suite BENCHMARK_CONVERSATIONS exists
to protect: every entry must still compare clean."""

from app.ai.evaluation import (
    BENCHMARK_CONVERSATIONS,
    PlanExpectation,
    compare_plan,
    run_benchmarks,
)
from app.ai.intent import ConversationCategory


def test_every_benchmark_conversation_matches_its_expectation():
    results = run_benchmarks()

    assert len(results) == len(BENCHMARK_CONVERSATIONS)
    failed = [r for r in results if not r.passed]
    assert failed == [], (
        f"benchmark(s) regressed: {[(r.expectation.text, r.mismatches) for r in failed]}"
    )


def test_compare_plan_reports_a_category_mismatch():
    expectation = PlanExpectation(text="Hi there!", category=ConversationCategory.ACTION)

    result = compare_plan(expectation)

    assert result.passed is False
    assert any("category" in m for m in result.mismatches)


def test_compare_plan_reports_a_domain_mismatch():
    expectation = PlanExpectation(
        text="Book a meeting with John tomorrow at 3 PM.",
        category=ConversationCategory.ACTION,
        domains=("crm",),
    )

    result = compare_plan(expectation)

    assert result.passed is False
    assert any("domains" in m for m in result.mismatches)


def test_compare_plan_reports_an_action_mismatch():
    expectation = PlanExpectation(
        text="Book a meeting with John tomorrow at 3 PM.",
        category=ConversationCategory.ACTION,
        domains=("calendar",),
        actions=("calendar_reschedule",),
    )

    result = compare_plan(expectation)

    assert result.passed is False
    assert any("actions" in m for m in result.mismatches)


def test_compare_plan_reports_a_missing_clarification_hint():
    expectation = PlanExpectation(
        text="Book a meeting with John tomorrow at 3 PM.",
        category=ConversationCategory.ACTION,
        domains=("calendar",),
        actions=("calendar_booking",),
        clarification_hint_expected=True,
    )

    result = compare_plan(expectation)

    assert result.passed is False
    assert any("clarification_hint" in m for m in result.mismatches)


def test_compare_plan_passes_when_everything_matches():
    expectation = PlanExpectation(
        text="Book a meeting with John tomorrow at 3 PM.",
        category=ConversationCategory.ACTION,
        domains=("calendar",),
        actions=("calendar_booking",),
    )

    result = compare_plan(expectation)

    assert result.passed is True
    assert result.mismatches == ()
