"""Cross-Employee Execution Planning (Sprint 75, DEC-045).

Combines app/ai/intent.py's multi-domain detection, app/ai/planning.py's
per-domain readiness, app/ai/governance.py's per-action policy, and
app/ai/roles.py's Employee Registry into one ordered, already-governed
ExecutionPlan. app/ai/orchestrator.py consumes this instead of inferring
tool exposure inline — "the execution engine should consume the plan rather
than infer behaviour dynamically" (Sprint 75, Objective B).

Planning only. Nothing here executes a tool, calls the LLM, or writes any
state — it only decides which tool schemas the model is even offered this
turn. Actual execution is entirely unchanged from Sprint 74
(app/ai/tools.py::response_to_message_fields + app/ai/processing.py /
app/ai/playground.py) — a plan step becoming a tool call the model actually
proposes, then a Message row, then pending_approval/auto-send, is exactly
the same pipeline as before this sprint.

Governance, not bypassed: every step with a named action gets its own
app/ai/governance.py::evaluate_execution() call before it's ever added to
the plan — this is the piece DEC-044 explicitly deferred rather than build
unsafely (offering a second domain's tools without evaluating that domain's
own policy). The moment one domain isn't ready or isn't
ExecutionDecision.EXECUTE_NOW, planning stops — every later domain is
simply never considered, "in parallel" or otherwise. This generalizes,
without weakening, the exact single-action gate app/ai/orchestrator.py used
before this sprint: a message matching only one domain produces an
identical-shape single-step (or zero-step) plan, so single-domain requests
behave exactly as before (Sprint 75 acceptance criterion 9).

Capped at app/ai/tools.py::MAX_TOOL_CALLS_PER_TURN (2) — the same constant
Sprint 74's execution layer already caps at, not a second number that could
drift out of sync. Planning three steps when only two could ever become
Message rows would be pure waste.

Sprint 80 (multi-turn intent continuity, DEC-049): build_execution_plan()
gained an optional `pending_domain` param — the domain a *prior* turn in
this same conversation was already working on, resolved by the caller via
app/services/execution_traces.py::get_pending_domain() (this module stays
DB-free; the caller does the lookup and hands in a plain string). Used only
when Stage 1 (app/ai/intent.py::classify_conversation) returns None for the
*current* message — genuinely ambiguous, not confidently anything else —
which is exactly what a bare "yes"/"sure, go ahead" is. `ExecutionPlan`
gained `active_domain`, recording whichever domain *this* turn ended up
using (whether or not it reached `steps` — a domain withheld pending more
detail is still "active"), so the next turn's get_pending_domain() has
something to find. A message that confidently classifies as something else
(a real greeting, a knowledge question, an explicit new action) always
takes precedence over an inherited pending domain — continuity only ever
fills a genuine gap, never overrides a clear signal.

Confirmation continuity (DEC-051): a narrower, distinct gap Sprint 80 didn't
cover — a governance-gated action (calendar_cancel, calendar_reschedule) that
planning.py already found fully specified gets withheld pending the
customer's confirmation, and the customer's reply naturally confirms in
words that echo the action's own trigger keyword ("yes, cancel it"). That
keyword match sends the confirmation text through app/ai/planning.py's
required-field check *again*, which — correctly, in isolation — finds the
short reply itself under-specified (the date/appointment reference was
supplied in the earlier turn that first made the action ready) and withholds
it a second time, asking the same question forever. `pending_action`
(persisted the same way as `pending_domain`, via
app/services/execution_traces.py::get_pending_action()) fixes this by
resuming the *already-validated* action directly on the confirmation turn —
skipping both planning's fresh field re-check and governance's own
re-evaluation (which would just ask for confirmation again) for that one
action — rather than re-deriving or re-validating anything from the
confirmation text itself. A domain-less confirmation ("Sure, please go
ahead.") already worked before this change via `pending_domain` alone
(planning finds no trigger keyword, passes every tool through generically);
this only fixes the case where the confirmation happens to name its own
action. Generic across every confirmation-gated action, present and future —
nothing here names calendar_cancel specifically.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.ai.governance import ExecutionDecision, evaluate_execution
from app.ai.intent import (
    ConversationCategory,
    classify_conversation,
    domains_for_action,
    tool_schemas_for_domain,
)
from app.ai.llm.base import ToolSchema
from app.ai.planning import ActionPlan, plan_actions
from app.ai.roles import role_for_tool
from app.ai.tools import MAX_TOOL_CALLS_PER_TURN


@dataclass(frozen=True)
class PlanStep:
    domain: str
    action: str | None
    role: str | None
    tools: tuple[ToolSchema, ...]


@dataclass(frozen=True)
class ExecutionPlan:
    category: ConversationCategory
    # Only steps that already cleared readiness + governance — never a
    # step the model shouldn't have been offered.
    steps: tuple[PlanStep, ...]
    # Set only when planning stopped early (an unready or ungoverned
    # domain) — folded into the system prompt exactly like Sprint 58/59's
    # single-action clarification_hint always was.
    clarification_hint: str | None = None
    # Sprint 80: the domain this turn was actually about, whether or not it
    # made it into `steps` — the one piece of state the *next* turn can
    # inherit if it turns out to be an ambiguous continuation. None for any
    # non-ACTION turn, or an ACTION turn where no domain matched at all.
    active_domain: str | None = None
    # DEC-051: the action name, if any, that planning.py already found fully
    # specified (ready=True) but governance withheld pending the customer's
    # own confirmation — distinct from active_domain because it marks an
    # *already-validated* action, not just "which domain," so the next
    # turn's confirmation can resume it directly instead of re-deriving it.
    # None whenever a withhold came from planning (missing information)
    # rather than governance (needs confirmation), and None once the action
    # actually gets offered (resumed or freshly EXECUTE_NOW).
    pending_action: str | None = None

    @property
    def tools(self) -> list[ToolSchema]:
        """The union of every included step's tools, in step order — what
        app/ai/orchestrator.py actually passes to llm.generate()."""
        return [tool for step in self.steps for tool in step.tools]


def build_execution_plan(
    text: str, *, pending_domain: str | None = None, pending_action: str | None = None
) -> ExecutionPlan:
    """The single entry point app/ai/orchestrator.py calls. Empty-steps
    plans (category != ACTION, or no domain matched, or the very first
    domain isn't ready/governed) behave exactly like "no tools offered"
    always did — this function's return shape makes that the uniform,
    zero-special-casing default rather than a caller-side check.

    `pending_domain` (Sprint 80) is consulted only when this message's own
    text is genuinely ambiguous (classify_conversation returns None) *and*
    domains_for_action() itself finds nothing for the current text either
    — a message's own domain match (including domains_for_action's own
    time-marker fallback, e.g. "Actually, create a lead for Priya" pivoting
    away from a pending calendar domain) always takes priority over an
    inherited one, same as any other confident classification.

    `pending_action` (DEC-051) is a separate, narrower axis — it's consulted
    inside the per-domain loop below, only when *this* domain's fresh
    plan_actions() result names the exact same action that's pending
    confirmation. It never affects domain selection above; a message that
    confidently names a different domain or a different action is handled
    entirely on its own terms, same as always.
    """
    category = classify_conversation(text)
    if category is None:
        domains = domains_for_action(text)
        if domains:
            category = ConversationCategory.ACTION
        elif pending_domain is not None:
            category = ConversationCategory.ACTION
            domains = [pending_domain]
        else:
            return ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
    elif category != ConversationCategory.ACTION:
        return ExecutionPlan(category=category, steps=())
    else:
        domains = domains_for_action(text)

    domains = domains[:MAX_TOOL_CALLS_PER_TURN]
    if not domains:
        return ExecutionPlan(category=category, steps=())
    active_domain = domains[0]

    steps: list[PlanStep] = []
    clarification_hint: str | None = None
    next_pending_action: str | None = None
    for domain, action_plan in zip(domains, plan_actions(text, domains)):
        if not action_plan.ready:
            if action_plan.action is not None and action_plan.action == pending_action:
                # DEC-051: this domain's own action matches what's pending
                # confirmation — resume the already-validated action rather
                # than trust this fresh (and here, spuriously negative)
                # required-field check against the confirmation text itself.
                action_plan = ActionPlan(ready=True, action=action_plan.action)
            else:
                clarification_hint = action_plan.clarification_hint
                break
        if action_plan.action is not None:
            if action_plan.action == pending_action:
                # Already passed governance in the turn that first asked for
                # confirmation — this turn *is* that confirmation, so
                # re-evaluating would only produce the same question again.
                pass
            else:
                # Only a *named*, ready action has a policy to enforce — an
                # action no ActionProfile recognises yet has none either,
                # matching plan_action()'s own pre-Sprint-75 pass-through (see
                # app/ai/orchestrator.py's original docstring, now here).
                governance = evaluate_execution(action_plan.action)
                if governance.decision != ExecutionDecision.EXECUTE_NOW:
                    clarification_hint = (
                        governance.confirmation_prompt
                        or governance.approval_reason
                        or governance.explanation
                    )
                    next_pending_action = action_plan.action
                    break
        tools = tuple(tool_schemas_for_domain(domain))
        role = role_for_tool(tools[0].name) if tools else None
        steps.append(PlanStep(domain=domain, action=action_plan.action, role=role, tools=tools))

    return ExecutionPlan(
        category=category,
        steps=tuple(steps),
        clarification_hint=clarification_hint,
        active_domain=active_domain,
        pending_action=next_pending_action,
    )
