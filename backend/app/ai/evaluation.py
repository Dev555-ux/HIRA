"""Execution plan evaluation framework (Sprint 76, DEC-047, Objective D).

Compares an expected plan *shape* against what app/ai/plan.py::build_execution_plan()
actually produces for a benchmark message. Planning is pure and deterministic
(no LLM, no DB) — Stage 1/2 classification, per-domain readiness, and
per-domain governance are all rule-based — so this can run as an ordinary,
fast, non-flaky regression suite (see tests/test_evaluation.py) rather than
needing a mocked LLM provider the way a real reply does.

This is explicitly a comparison framework, not automatic prompt improvement:
nothing here mutates a prompt, scores a model, or picks a "better" version of
anything. It answers one question — "does today's planning logic still
produce the plan we expect for this message?" — the same question a human
would ask by hand, just runnable in CI.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.intent import ConversationCategory
from app.ai.plan import ExecutionPlan, build_execution_plan


@dataclass(frozen=True)
class PlanExpectation:
    text: str
    category: ConversationCategory
    # Expected step domains/actions, in order — empty means "no steps".
    domains: tuple[str, ...] = ()
    actions: tuple[str | None, ...] = ()
    # Whether *any* clarification_hint is expected — hint wording itself
    # isn't a stable contract (it's assembled from governance/planning
    # explanation text), so only presence/absence is checked.
    clarification_hint_expected: bool = False


@dataclass(frozen=True)
class PlanComparisonResult:
    expectation: PlanExpectation
    actual: ExecutionPlan
    passed: bool
    mismatches: tuple[str, ...]


def compare_plan(expectation: PlanExpectation) -> PlanComparisonResult:
    actual = build_execution_plan(expectation.text)
    mismatches: list[str] = []

    if actual.category != expectation.category:
        mismatches.append(
            f"category: expected {expectation.category.value!r}, got {actual.category.value!r}"
        )

    actual_domains = tuple(step.domain for step in actual.steps)
    if actual_domains != expectation.domains:
        mismatches.append(f"domains: expected {expectation.domains!r}, got {actual_domains!r}")

    actual_actions = tuple(step.action for step in actual.steps)
    if actual_actions != expectation.actions:
        mismatches.append(f"actions: expected {expectation.actions!r}, got {actual_actions!r}")

    has_hint = actual.clarification_hint is not None
    if has_hint != expectation.clarification_hint_expected:
        mismatches.append(
            "clarification_hint: expected "
            f"{'present' if expectation.clarification_hint_expected else 'absent'}, got "
            f"{'present' if has_hint else 'absent'}"
        )

    return PlanComparisonResult(
        expectation=expectation, actual=actual, passed=not mismatches, mismatches=tuple(mismatches)
    )


# Benchmark conversations (Objective D): a small, hand-picked set spanning
# every planning outcome build_execution_plan() can produce — no steps,
# single step, multi-step, and stopped-early (unready/ungoverned). Doubles as
# the regression suite in tests/test_evaluation.py; add a case here whenever
# a planning bug is fixed, so it can't silently regress.
BENCHMARK_CONVERSATIONS: tuple[PlanExpectation, ...] = (
    PlanExpectation(text="Hi there!", category=ConversationCategory.CONVERSATION),
    PlanExpectation(
        text="Book a meeting with John tomorrow at 3 PM.",
        category=ConversationCategory.ACTION,
        domains=("calendar",),
        actions=("calendar_booking",),
    ),
    PlanExpectation(
        text="Book a meeting tomorrow at 10am and create a lead for John.",
        category=ConversationCategory.ACTION,
        domains=("calendar", "crm"),
        actions=("calendar_booking", "crm_lead"),
    ),
    PlanExpectation(
        text="Book a meeting tomorrow at 10am and create a lead.",  # no name for the lead
        category=ConversationCategory.ACTION,
        domains=("calendar",),
        actions=("calendar_booking",),
        clarification_hint_expected=True,
    ),
    PlanExpectation(
        text="Cancel my appointment for tomorrow and create a lead for John.",
        category=ConversationCategory.ACTION,
        clarification_hint_expected=True,
    ),
)


def run_benchmarks(
    benchmarks: tuple[PlanExpectation, ...] = BENCHMARK_CONVERSATIONS,
) -> list[PlanComparisonResult]:
    return [compare_plan(expectation) for expectation in benchmarks]
