"""Shared aggregation functions for both the Founder Operations Dashboard
(cross-tenant, `app/services/founder_ops.py`) and the per-business Analytics
page (`app/api/analytics.py`).

Every function here accepts an optional `business_id`: omitted, it aggregates
across every business (the founder's cross-tenant view); passed, it adds one
extra WHERE clause and returns the same shape scoped to that business. This
is the single source of truth for these queries — neither caller re-derives
the SQL, so the two views can never drift apart on how a figure is computed.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import Integer, func, select
from sqlalchemy.orm import Session

from app.core.time import to_iso_utc
from app.models import (
    Appointment,
    Conversation,
    Escalation,
    ExecutionTrace,
    KbEntry,
    Lead,
    Message,
    WhatsAppCredential,
)
from app.services.execution_traces import get_result_messages, get_trace, list_traces, resolve_outcome  # noqa: F401  (re-exported for founder_ops.py's trace endpoints)

# Rough estimate for the "human work saved" AI Impact figure — not a
# measured benchmark. ponytail: revisit if a real time-and-motion number
# ever becomes available; until then this is clearly labeled as an estimate
# wherever it's surfaced.
MINUTES_SAVED_PER_AI_REPLY = 4


def iso(value: datetime | None) -> str | None:
    return to_iso_utc(value)


def conversation_counts(db: Session, business_id: uuid.UUID | None = None) -> dict[uuid.UUID, int]:
    stmt = select(Conversation.business_id, func.count().label("n")).group_by(Conversation.business_id)
    if business_id is not None:
        stmt = stmt.where(Conversation.business_id == business_id)
    return {row.business_id: row.n for row in db.execute(stmt).all()}


def message_stats(
    db: Session, *, recent_failure_cutoff: datetime, business_id: uuid.UUID | None = None
) -> dict[uuid.UUID, dict]:
    """One grouped query for every per-business message-derived metric —
    outbound count (AI responses), failure counts (all-time and recent), and
    last inbound/outbound/any-direction timestamps (last activity)."""
    stmt = select(
        Message.business_id,
        func.count().filter(Message.direction == "outbound").label("ai_responses"),
        func.count().filter(Message.status == "failed").label("failed_responses"),
        func.count()
        .filter(Message.status == "failed", Message.created_at >= recent_failure_cutoff)
        .label("recent_failed_responses"),
        func.max(Message.created_at).filter(Message.direction == "inbound").label("last_inbound_at"),
        func.max(Message.created_at).filter(Message.direction == "outbound").label("last_outbound_at"),
        func.max(Message.created_at).label("last_activity_at"),
    ).group_by(Message.business_id)
    if business_id is not None:
        stmt = stmt.where(Message.business_id == business_id)
    rows = db.execute(stmt).all()
    return {
        row.business_id: {
            "ai_responses": row.ai_responses,
            "failed_responses": row.failed_responses,
            "recent_failed_responses": row.recent_failed_responses,
            "last_inbound_at": row.last_inbound_at,
            "last_outbound_at": row.last_outbound_at,
            "last_activity_at": row.last_activity_at,
        }
        for row in rows
    }


def response_time_seconds_by_business(
    db: Session, business_id: uuid.UUID | None = None
) -> dict[uuid.UUID, float]:
    """Average seconds between an inbound message and the very next message in
    that same conversation, when that next message is outbound — the real "AI
    response time," computed in one window-function query. `LAG` requires a
    subquery since you can't filter directly on a window function in the same
    SELECT it's defined in."""
    prev_created_at = func.lag(Message.created_at).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    prev_direction = func.lag(Message.direction).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    turns_query = select(
        Message.business_id.label("business_id"),
        Message.direction.label("direction"),
        Message.created_at.label("created_at"),
        prev_created_at.label("prev_created_at"),
        prev_direction.label("prev_direction"),
    )
    if business_id is not None:
        turns_query = turns_query.where(Message.business_id == business_id)
    turns = turns_query.subquery()

    rows = db.execute(
        select(
            turns.c.business_id,
            func.avg(func.extract("epoch", turns.c.created_at - turns.c.prev_created_at)).label(
                "avg_seconds"
            ),
        )
        .where(turns.c.direction == "outbound", turns.c.prev_direction == "inbound")
        .group_by(turns.c.business_id)
    ).all()
    return {row.business_id: float(row.avg_seconds) for row in rows if row.avg_seconds is not None}


def overall_response_time_seconds(db: Session, business_id: uuid.UUID | None = None) -> float | None:
    """Same computation as `response_time_seconds_by_business`, but ungrouped
    — a genuine average across every qualifying turn (platform-wide, or for
    one business), not an average-of-per-business-averages (which would
    over-weight low-volume businesses when unscoped)."""
    prev_created_at = func.lag(Message.created_at).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    prev_direction = func.lag(Message.direction).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    turns_query = select(
        Message.direction.label("direction"),
        Message.created_at.label("created_at"),
        prev_created_at.label("prev_created_at"),
        prev_direction.label("prev_direction"),
    )
    if business_id is not None:
        turns_query = turns_query.where(Message.business_id == business_id)
    turns = turns_query.subquery()

    result = db.execute(
        select(func.avg(func.extract("epoch", turns.c.created_at - turns.c.prev_created_at))).where(
            turns.c.direction == "outbound", turns.c.prev_direction == "inbound"
        )
    ).scalar()
    return float(result) if result is not None else None


def kb_stats(db: Session, business_id: uuid.UUID | None = None) -> dict[uuid.UUID, dict]:
    stmt = select(
        KbEntry.business_id,
        func.count().filter(KbEntry.status == "published").label("published_count"),
        func.count().filter(KbEntry.status == "draft").label("draft_count"),
        func.max(KbEntry.updated_at).label("last_updated_at"),
    ).group_by(KbEntry.business_id)
    if business_id is not None:
        stmt = stmt.where(KbEntry.business_id == business_id)
    rows = db.execute(stmt).all()
    return {
        row.business_id: {
            "published_count": row.published_count,
            "draft_count": row.draft_count,
            "last_updated_at": row.last_updated_at,
        }
        for row in rows
    }


def businesses_with_stored_credential(db: Session) -> set[uuid.UUID]:
    return set(db.scalars(select(WhatsAppCredential.business_id)))


def today_totals(
    db: Session, *, since: datetime, business_id: uuid.UUID | None = None
) -> dict[str, int]:
    stmt = select(
        func.count().label("messages_today"),
        func.count().filter(Message.direction == "outbound").label("ai_responses_today"),
        func.count().filter(Message.status == "failed").label("failed_responses_today"),
    ).where(Message.created_at >= since)
    if business_id is not None:
        stmt = stmt.where(Message.business_id == business_id)
    row = db.execute(stmt).one()
    return {
        "messages_today": row.messages_today,
        "ai_responses_today": row.ai_responses_today,
        "failed_responses_today": row.failed_responses_today,
    }


def business_alerts(
    *,
    whatsapp_connected: bool,
    kb_published_count: int,
    recent_failed_responses: int,
    last_activity_at: datetime | None,
    now: datetime,
    stale_activity_window,
) -> list[str]:
    alerts: list[str] = []
    if not whatsapp_connected:
        alerts.append("whatsapp_disconnected")
    if kb_published_count == 0:
        alerts.append("missing_knowledge_base")
    if recent_failed_responses > 0:
        alerts.append("ai_failures")
    if whatsapp_connected and (
        last_activity_at is None or now - last_activity_at > stale_activity_window
    ):
        alerts.append("no_recent_activity")
    return alerts


def ai_metrics(db: Session, business_id: uuid.UUID | None = None) -> dict:
    """AI Employee observability, aggregated from every `ExecutionTrace` row —
    across every business when `business_id` is omitted, or scoped to one.
    Two bulk queries (traces, then their result Messages), never one per
    trace. Grouping by values *inside* a JSONB array (proposed_tool_calls)
    doesn't fit a plain GROUP BY, so this aggregates in Python instead."""
    stmt = select(ExecutionTrace)
    if business_id is not None:
        stmt = stmt.where(ExecutionTrace.business_id == business_id)
    traces = list(db.scalars(stmt))
    if not traces:
        return {
            "total_turns": 0,
            "employee_utilisation": {},
            "most_used_employee": None,
            "most_used_tools": [],
            "failed_tool_executions": 0,
            "governance_blocks": 0,
            "avg_plan_length": 0.0,
            "avg_execution_time_ms": 0.0,
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

    employee_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    plan_lengths: list[int] = []
    durations: list[int] = []
    governance_blocks = 0
    failed_tool_executions = 0

    for trace in traces:
        plan_lengths.append(len(trace.plan.get("steps", [])))
        durations.append(trace.duration_ms)
        if trace.plan.get("clarification_hint") is not None:
            governance_blocks += 1
        for call in trace.proposed_tool_calls:
            tool_name = call.get("tool_name")
            agent_role = call.get("agent_role")
            if tool_name:
                tool_counts[tool_name] += 1
            if agent_role:
                employee_counts[agent_role] += 1
        result_messages = [
            messages_by_id[uuid.UUID(message_id)]
            for message_id in trace.result_message_ids
            if uuid.UUID(message_id) in messages_by_id
        ]
        if trace.proposed_tool_calls and resolve_outcome(result_messages) == "failed":
            failed_tool_executions += 1

    return {
        "total_turns": len(traces),
        "employee_utilisation": dict(employee_counts),
        "most_used_employee": employee_counts.most_common(1)[0][0] if employee_counts else None,
        "most_used_tools": [
            {"tool_name": name, "count": count} for name, count in tool_counts.most_common(5)
        ],
        "failed_tool_executions": failed_tool_executions,
        "governance_blocks": governance_blocks,
        "avg_plan_length": sum(plan_lengths) / len(plan_lengths),
        "avg_execution_time_ms": sum(durations) / len(durations),
    }


def daily_counts(
    db: Session, model, date_column, *, business_id: uuid.UUID, since: datetime, until: datetime
) -> dict[date, int]:
    """One day-bucketed COUNT query for any model with a business_id and a
    timestamp column. Days with zero rows are simply absent from the
    result — callers needing a gap-free series use `fill_daily`."""
    stmt = (
        select(func.date_trunc("day", date_column).label("day"), func.count().label("n"))
        .where(model.business_id == business_id, date_column >= since, date_column <= until)
        .group_by("day")
    )
    return {row.day.date(): row.n for row in db.execute(stmt).all()}


def fill_daily(counts: dict[date, int], since: datetime, until: datetime) -> list[dict]:
    """Turns a sparse {date: count} map into a gap-free day-by-day series —
    charts need every day present, not just the ones with activity."""
    num_days = (until.date() - since.date()).days
    return [
        {
            "date": (since.date() + timedelta(days=offset)).isoformat(),
            "count": counts.get(since.date() + timedelta(days=offset), 0),
        }
        for offset in range(num_days + 1)
    ]


def trends(db: Session, business_id: uuid.UUID, *, since: datetime, until: datetime) -> dict:
    """Day-bucketed series for the Analytics page's Trends section: one
    query per metric (they're different tables, so this can't collapse into
    a single grouped query), each gap-filled to a full day-by-day series."""
    return {
        "conversations": fill_daily(
            daily_counts(db, Conversation, Conversation.created_at, business_id=business_id, since=since, until=until),
            since,
            until,
        ),
        "messages": fill_daily(
            daily_counts(db, Message, Message.created_at, business_id=business_id, since=since, until=until),
            since,
            until,
        ),
        "leads": fill_daily(
            daily_counts(db, Lead, Lead.created_at, business_id=business_id, since=since, until=until),
            since,
            until,
        ),
        "appointments": fill_daily(
            daily_counts(db, Appointment, Appointment.created_at, business_id=business_id, since=since, until=until),
            since,
            until,
        ),
    }


def ai_impact(db: Session, business_id: uuid.UUID, *, since: datetime, until: datetime) -> dict:
    """The mandatory AI Impact section: what the AI Employee actually did
    for this business in the selected range, in business terms rather than
    engineering terms."""

    def count(model, *filters) -> int:
        stmt = select(func.count()).select_from(model).where(
            model.business_id == business_id, model.created_at.between(since, until), *filters
        )
        return db.scalar(stmt) or 0

    ai_responses = count(Message, Message.direction == "outbound")
    kb_grounded_replies = count(
        Message,
        Message.direction == "outbound",
        Message.ai_meta["retrieved_count"].astext.cast(Integer) > 0,
    )

    return {
        "conversations_handled": count(Conversation),
        "human_escalations": count(Escalation),
        "leads_created": count(Lead),
        "appointments_booked": count(Appointment),
        "kb_grounded_replies": kb_grounded_replies,
        "ai_responses": ai_responses,
        "estimated_hours_saved": round(ai_responses * MINUTES_SAVED_PER_AI_REPLY / 60, 1),
    }


def status_breakdown(db: Session, model, status_column, business_id: uuid.UUID) -> dict[str, int]:
    """Generic current-state breakdown (conversation status, lead stage,
    appointment status, lead source, ...) — grouped count on whichever
    column the caller passes, always scoped to one business."""
    stmt = (
        select(status_column, func.count())
        .where(model.business_id == business_id)
        .group_by(status_column)
    )
    return dict(db.execute(stmt).all())
