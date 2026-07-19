"""Execution Governance (Sprint 59) — a policy layer, not another planning
stage.

Builds directly on Sprint 58 (app/ai/planning.py): once a message is ready
to act on (plan_action() returned ready=True with a named action, e.g.
"calendar_booking"), this module decides *how* it may execute — immediately,
only after confirming with the customer, only after a human reviews it, or
not at all. It answers "is this action allowed to run automatically," never
"does this message contain enough detail" (that's Sprint 58) or "which tool
group applies" (that's Sprint 57's app/ai/intent.py).

This module knows nothing about LLMs, prompt construction, providers, or
HTTP — it takes an action name (a plain string) and returns a
GovernanceResult. app/ai/orchestrator.py is the only caller, and it's the
one that decides what to *do* with the result (fold a hint into the system
prompt, same as it already does for Sprint 58's clarification_hint).

Extending with a new action's policy means adding one GovernancePolicy
entry to _POLICIES below — no other code changes. Some entries here
(invoice_send, refund, delete_customer, ...) name actions that have no real
tool or Planning profile yet (see app/ai/tools.py, app/ai/planning.py) —
they exist as forward-declared policy for capabilities not built yet, per
this sprint's "design for future AI employees and future tool categories."
An action with no matching Planning profile never reaches this module in
practice (app/ai/orchestrator.py only calls evaluate_execution() once
Sprint 58 names an action); evaluate_execution() itself is exercised
directly against these names in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ExecutionDecision(str, Enum):
    EXECUTE_NOW = "execute_now"
    REQUIRES_CONFIRMATION = "requires_confirmation"
    REQUIRES_HUMAN_APPROVAL = "requires_human_approval"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class GovernanceResult:
    decision: ExecutionDecision
    explanation: str | None = None
    # A hint folded into the system prompt (app/ai/prompts.py), same shape
    # as Sprint 58's clarification_hint — never literal customer-facing
    # text; the model phrases the actual question.
    confirmation_prompt: str | None = None
    approval_reason: str | None = None


@dataclass(frozen=True)
class GovernancePolicy:
    action: str
    decision: ExecutionDecision
    explanation: str | None = None
    confirmation_prompt: str | None = None
    approval_reason: str | None = None


_POLICIES: dict[str, GovernancePolicy] = {
    policy.action: policy
    for policy in (
        GovernancePolicy(
            action="calendar_booking",
            decision=ExecutionDecision.EXECUTE_NOW,
            explanation="Booking a new appointment is routine and easily reversed by cancelling it.",
        ),
        GovernancePolicy(
            action="calendar_reschedule",
            decision=ExecutionDecision.REQUIRES_CONFIRMATION,
            explanation="Rescheduling replaces a commitment the customer already made.",
            confirmation_prompt=(
                "confirm with the customer that they want to move their existing appointment to "
                "the new date/time before treating it as done"
            ),
        ),
        GovernancePolicy(
            action="calendar_cancel",
            decision=ExecutionDecision.REQUIRES_CONFIRMATION,
            explanation="Cancelling removes a commitment the customer already made.",
            confirmation_prompt=(
                "confirm with the customer that they really want to cancel this appointment "
                "before treating it as done"
            ),
        ),
        GovernancePolicy(
            action="crm_lead",
            decision=ExecutionDecision.EXECUTE_NOW,
            explanation="Logging a new lead is routine bookkeeping with no customer-facing side effect.",
        ),
        # Future actions: no tool or Planning profile exists yet for any of
        # these (see this module's docstring) — declared here so the policy
        # is already in place the moment the capability is built.
        GovernancePolicy(
            action="crm_lead_delete",
            decision=ExecutionDecision.REQUIRES_CONFIRMATION,
            explanation="Deleting a lead discards history that can't be recovered automatically.",
            confirmation_prompt=(
                "confirm which lead they mean and that they really want it deleted before "
                "treating it as done"
            ),
        ),
        GovernancePolicy(
            action="invoice_send",
            decision=ExecutionDecision.REQUIRES_CONFIRMATION,
            explanation="Sending an invoice creates a customer-visible financial document.",
            confirmation_prompt="confirm the amount and recipient with the customer before sending",
        ),
        GovernancePolicy(
            action="send_email",
            decision=ExecutionDecision.REQUIRES_CONFIRMATION,
            explanation="Outbound email is customer-visible and can't be recalled once sent.",
            confirmation_prompt="confirm the content and recipient before sending",
        ),
        GovernancePolicy(
            action="whatsapp_broadcast",
            decision=ExecutionDecision.REQUIRES_HUMAN_APPROVAL,
            explanation="A broadcast reaches many customers at once — a mistake isn't recoverable.",
            approval_reason="Bulk outbound messaging needs a human to review it before it goes out.",
        ),
        GovernancePolicy(
            action="refund",
            decision=ExecutionDecision.REQUIRES_HUMAN_APPROVAL,
            explanation="Refunds move real money and directly affect the business's revenue.",
            approval_reason="Financial reversals need a human to review the amount and reason first.",
        ),
        GovernancePolicy(
            action="payment",
            decision=ExecutionDecision.REQUIRES_HUMAN_APPROVAL,
            explanation="Payments move real money.",
            approval_reason="Anything that moves money needs a human to review it first.",
        ),
        GovernancePolicy(
            action="delete_customer",
            decision=ExecutionDecision.REQUIRES_HUMAN_APPROVAL,
            explanation="Deleting a customer permanently removes their record and history.",
            approval_reason="Irreversible data deletion needs a human to confirm before it happens.",
        ),
        GovernancePolicy(
            action="update_business_data",
            decision=ExecutionDecision.REQUIRES_HUMAN_APPROVAL,
            explanation="Business-level data (hours, pricing, policies) affects every future conversation.",
            approval_reason="Changes here affect all customers, not just this one, so a human reviews first.",
        ),
    )
}


def evaluate_execution(action: str | None) -> GovernanceResult:
    """The single entry point: given an action name (app/ai/planning.py's
    ActionPlan.action), returns the policy decision for it.

    No action, or an action with no registered policy, is BLOCKED with a
    helpful explanation — never EXECUTE_NOW by default. An unrecognised
    action is exactly the case a policy layer exists to catch; silently
    allowing it through would defeat the purpose.
    """
    if action is None:
        return GovernanceResult(
            decision=ExecutionDecision.BLOCKED,
            explanation="No specific action was identified to evaluate a policy for.",
        )
    policy = _POLICIES.get(action)
    if policy is None:
        return GovernanceResult(
            decision=ExecutionDecision.BLOCKED,
            explanation=(
                f"'{action}' has no execution policy defined yet, so it can't run "
                "automatically until one is added."
            ),
        )
    return GovernanceResult(
        decision=policy.decision,
        explanation=policy.explanation,
        confirmation_prompt=policy.confirmation_prompt,
        approval_reason=policy.approval_reason,
    )
