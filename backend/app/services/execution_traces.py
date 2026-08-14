"""Execution trace recording and retrieval (Sprint 76, DEC-047).

Write-once: `record_execution_trace()` is called exactly once per customer
turn, right after app/ai/tools.py::response_to_message_fields() has decided
what Message rows this turn produces. Nothing here is ever updated in place —
"execution outcome" for a proposed action (approved/rejected/sent/failed,
possibly asynchronously, by app/services/replies.py) is derived at *read*
time by joining `result_message_ids` to those Messages' current state, so
this module never needs to reach into or mutate the approval flow.

Read helpers here back both Founder Ops (Objective B: AI metrics, Objective
C: replay) and app/ai/evaluation.py (Objective D) — one place that knows how
to turn a trace + its current Messages into a coherent "what happened". Sprint
84 (Dashboard Foundation) adds a third reader: the owner-facing "AI activity"
feed (`list_activity_for_dashboard` / `summarize_activity` below) — the same
traces, read back as a one-line narrative instead of Founder Ops's replay-list
shape. No new signal, only a new read of data already durably stored per turn.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import to_iso_utc

from app.ai.plan import ExecutionPlan
from app.models import Conversation, Customer, ExecutionTrace, Message


def _serialize_plan(plan: ExecutionPlan) -> dict:
    return {
        "category": plan.category.value,
        "steps": [
            {
                "domain": step.domain,
                "action": step.action,
                "role": step.role,
                "tools": [tool.name for tool in step.tools],
            }
            for step in plan.steps
        ],
        "clarification_hint": plan.clarification_hint,
        "active_domain": plan.active_domain,
        "pending_action": plan.pending_action,
    }


def record_execution_trace(
    db: Session,
    *,
    business_id: uuid.UUID,
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID | None,
    plan: ExecutionPlan,
    proposed_tool_calls: list[dict],
    result_message_ids: list[uuid.UUID],
    duration_ms: int,
) -> ExecutionTrace:
    """Flushes (does not commit) — callers persist the trace atomically with
    the Message rows it describes, same "all lands or none does" guarantee
    app/ai/processing.py's Section A4 commit already gives those rows.
    """
    trace = ExecutionTrace(
        business_id=business_id,
        conversation_id=conversation_id,
        trigger_message_id=trigger_message_id,
        category=plan.category.value,
        plan=_serialize_plan(plan),
        proposed_tool_calls=proposed_tool_calls,
        result_message_ids=[str(message_id) for message_id in result_message_ids],
        duration_ms=duration_ms,
    )
    db.add(trace)
    db.flush()
    return trace


def get_trace(
    db: Session, trace_id: uuid.UUID, *, business_id: uuid.UUID | None = None
) -> ExecutionTrace | None:
    trace = db.get(ExecutionTrace, trace_id)
    if trace is None:
        return None
    if business_id is not None and trace.business_id != business_id:
        return None
    return trace


def list_traces(
    db: Session, *, business_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
) -> list[ExecutionTrace]:
    query = select(ExecutionTrace).order_by(ExecutionTrace.created_at.desc())
    if business_id is not None:
        query = query.where(ExecutionTrace.business_id == business_id)
    return list(db.scalars(query.limit(limit).offset(offset)))


def get_result_messages(db: Session, trace: ExecutionTrace) -> list[Message]:
    """The trace's `result_message_ids`, resolved to their *current* Message
    rows, in the original order — the join this whole write-once design
    exists to make possible, not a duplicate copy of status/tool_result.
    """
    message_ids = [uuid.UUID(raw_id) for raw_id in trace.result_message_ids]
    if not message_ids:
        return []
    rows = {
        message.id: message
        for message in db.scalars(select(Message).where(Message.id.in_(message_ids)))
    }
    return [rows[message_id] for message_id in message_ids if message_id in rows]


def _most_recent_trace(db: Session, conversation_id: uuid.UUID) -> ExecutionTrace | None:
    """Shared by get_pending_domain/get_pending_action — both ask the same
    "is this conversation mid-workflow" question, just about a different
    field of the same most-recent trace."""
    return db.scalars(
        select(ExecutionTrace)
        .where(ExecutionTrace.conversation_id == conversation_id)
        .order_by(ExecutionTrace.created_at.desc())
        .limit(1)
    ).first()


def get_pending_domain(db: Session, conversation_id: uuid.UUID) -> str | None:
    """Sprint 80 (multi-turn intent continuity, DEC-049): is this
    conversation mid-workflow? Looks at only the single most recent trace —
    if it was action-shaped (`plan["active_domain"]` set) and no write tool
    was actually proposed yet (`proposed_tool_calls` empty — check_availability
    never appears here, see app/ai/orchestrator.py, so "empty" specifically
    means no book/reschedule/cancel/CRM call happened), that domain is still
    open and the next ambiguous reply should continue it. A domain clears
    itself automatically the moment a write tool *is* proposed (the next
    trace's own proposed_tool_calls is then non-empty) or the current
    message classifies as something confident on its own (app/ai/plan.py
    only consults this for a None/ambiguous Stage 1 result) — no explicit
    "clear pending state" step anywhere, by construction.

    Read-only, single indexed query (conversation_id, created_at) — no
    heavier than the read helpers above.
    """
    trace = _most_recent_trace(db, conversation_id)
    if trace is None:
        return None
    plan = trace.plan or {}
    if plan.get("category") != "action":
        return None
    if trace.proposed_tool_calls:
        return None
    return plan.get("active_domain")


def get_pending_action(db: Session, conversation_id: uuid.UUID) -> str | None:
    """DEC-051: the narrower counterpart to get_pending_domain — was there an
    action planning.py already found fully specified, that governance then
    withheld pending the customer's own confirmation (`plan["pending_action"]`
    set)? If so, app/ai/plan.py::build_execution_plan() resumes that
    already-validated action directly on the confirmation turn rather than
    re-deriving it from the (naturally under-specified) confirmation text.
    Same self-clearing-by-construction design as get_pending_domain: a write
    tool actually being proposed clears it (proposed_tool_calls non-empty on
    the next trace), and so does the action simply being resumed and offered
    this turn (build_execution_plan only sets pending_action again if
    governance withholds it again, which a resumed action skips).
    """
    trace = _most_recent_trace(db, conversation_id)
    if trace is None:
        return None
    plan = trace.plan or {}
    if plan.get("category") != "action":
        return None
    if trace.proposed_tool_calls:
        return None
    return plan.get("pending_action")


def resolve_outcome(messages: list[Message]) -> str:
    """One word summarizing a trace's current execution outcome, from its
    resolved result Messages' statuses:

    - "no_result": the plan never produced a Message (empty/non-action turn).
    - "failed": at least one result Message failed (tool execution or send),
      *or* (Sprint 77) carries a live ai_meta["failure_reason"] — Autonomous
      Mode's honest fallback text (app/ai/processing.py::_auto_send) means a
      failed tool call can still end with status == "sent" once its fallback
      goes out, so status alone can no longer answer "did this turn's actual
      request succeed." failure_reason is the authoritative signal now.
    - "escalated": at least one result Message was escalated.
    - "rejected": at least one result Message was rejected in Assisted Mode.
    - "pending_approval": at least one result Message is still awaiting a
      human decision in Assisted Mode.
    - "sending": a send is still in flight.
    - "sent": every result Message reached a terminal, successful state.
    """
    if not messages:
        return "no_result"
    if any((message.ai_meta or {}).get("failure_reason") for message in messages):
        return "failed"
    statuses = {message.status for message in messages}
    for status in ("failed", "escalated", "rejected", "pending_approval", "sending"):
        if status in statuses:
            return status
    return "sent"


# Action name (from an ExecutionPlan step, app/ai/governance.py's vocabulary)
# -> a past-tense sentence template. Only the two actions actually cleared for
# EXECUTE_NOW today (calendar_booking, crm_lead) plus the two that reach
# "sent" via in-chat confirmation (calendar_reschedule, calendar_cancel) have
# real traces to summarize; anything else falls through to the generic
# fallback in summarize_activity() below rather than guessing a phrase for a
# capability that doesn't exist yet (refund, payment, ... — see governance.py).
_ACTION_PHRASES: dict[str, str] = {
    "calendar_booking": "Booked an appointment for {name}",
    "calendar_reschedule": "Rescheduled {name}'s appointment",
    "calendar_cancel": "Cancelled {name}'s appointment",
    "crm_lead": "Logged {name} as a new lead",
}


def summarize_activity(
    *,
    category: str,
    action: str | None,
    outcome: str,
    customer_name: str,
    retrieved_count: int | None,
) -> str:
    """One past-tense sentence for the owner-facing AI Activity feed. Every
    branch reads a real field off the trace/outcome — nothing here is
    fabricated (Dashboard Foundation spec's "show finished work, not raw
    logs" principle). `outcome` takes precedence over `category`: a trace
    that ended up escalated or failed says so, regardless of what it was
    originally trying to do.
    """
    if outcome == "escalated":
        return f"Escalated a message from {customer_name} to you"
    if outcome == "failed":
        return f"Couldn't send a reply to {customer_name} — check Escalations"
    if outcome == "rejected":
        return f"You rejected a drafted reply to {customer_name}"
    if outcome == "pending_approval":
        return f"Drafted a reply for {customer_name}, waiting on your approval"
    if outcome == "sending":
        return f"Sending a reply to {customer_name}…"

    # outcome == "sent"
    if category == "action" and action in _ACTION_PHRASES:
        return _ACTION_PHRASES[action].format(name=customer_name)
    if category == "knowledge":
        base = f"Answered a question from {customer_name}"
        if retrieved_count:
            source_word = "source" if retrieved_count == 1 else "sources"
            return f"{base}, grounded in {retrieved_count} knowledge {source_word}"
        return base
    if category == "capability":
        return f"Told {customer_name} what HIRA can help with"
    return f"Replied to {customer_name}"


def list_activity_for_dashboard(
    db: Session, *, business_id: uuid.UUID, limit: int = 20, offset: int = 0
) -> list[dict]:
    """Owner-facing "AI activity" feed (Sprint 84, Dashboard Foundation) —
    the same execution_traces this module already records, read back as a
    narrative instead of Founder Ops's replay-list shape (see
    app/services/founder_ops.py::list_traces_for_dashboard for that reader).
    Traces with no real outcome ("no_result" — an empty/non-action turn)
    are dropped; there's nothing to narrate. Bulk-loads customers and result
    messages the same way founder_ops does, so cost scales with the number
    of query round trips, not the number of traces returned.
    """
    traces = list_traces(db, business_id=business_id, limit=limit, offset=offset)
    if not traces:
        return []

    conversation_ids = {trace.conversation_id for trace in traces}
    customers_by_conversation = {
        row[0]: row[1]
        for row in db.execute(
            select(Conversation.id, Customer)
            .join(Customer, Customer.id == Conversation.customer_id)
            .where(Conversation.id.in_(conversation_ids))
        ).all()
    }

    all_result_ids = {
        uuid.UUID(message_id) for trace in traces for message_id in trace.result_message_ids
    }
    messages_by_id = {}
    if all_result_ids:
        messages_by_id = {
            message.id: message
            for message in db.scalars(select(Message).where(Message.id.in_(all_result_ids)))
        }

    rows = []
    for trace in traces:
        result_messages = [
            messages_by_id[uuid.UUID(message_id)]
            for message_id in trace.result_message_ids
            if uuid.UUID(message_id) in messages_by_id
        ]
        outcome = resolve_outcome(result_messages)
        if outcome == "no_result":
            continue

        customer = customers_by_conversation.get(trace.conversation_id)
        customer_name = customer.display_name if customer and customer.display_name else "a customer"

        steps = trace.plan.get("steps") or []
        action = steps[0].get("action") if steps else None

        retrieved_count = None
        for message in reversed(result_messages):
            if message.direction == "outbound":
                count = (message.ai_meta or {}).get("retrieved_count")
                if isinstance(count, int):
                    retrieved_count = count
                    break

        rows.append(
            {
                "id": str(trace.id),
                "conversation_id": str(trace.conversation_id),
                "customer": (
                    {"id": str(customer.id), "display_name": customer.display_name}
                    if customer
                    else None
                ),
                "category": trace.category,
                "outcome": outcome,
                "summary": summarize_activity(
                    category=trace.category,
                    action=action,
                    outcome=outcome,
                    customer_name=customer_name,
                    retrieved_count=retrieved_count,
                ),
                "created_at": to_iso_utc(trace.created_at),
            }
        )
    return rows
