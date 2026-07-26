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
to turn a trace + its current Messages into a coherent "what happened".
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.plan import ExecutionPlan
from app.models import ExecutionTrace, Message


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
