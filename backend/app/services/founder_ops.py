"""Founder Operations Dashboard aggregates (Sprint 73) — a deliberately
cross-tenant, read-only view for `app/api/founder_ops.py`. Every query here
is grouped by `business_id` in bulk (never a per-business loop), so the cost
of this dashboard scales with the number of *query round trips* (fixed,
small), not the number of businesses — the "suitable for future growth"
requirement this sprint asked for.

This intentionally does not use `app/db/tenant.py`'s `tenant_query`/
`get_scoped` — both raise if you don't pass a `business_id`, which is the
whole point here. This module is the one deliberate, audited hole in an
otherwise tenant-scoped codebase; see `get_founder_principal` in
app/auth/dependencies.py for how access to it is gated.
"""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Business, Conversation, ExecutionTrace, KbEntry, Message, WhatsAppCredential
from app.services.execution_traces import (
    get_result_messages,
    get_trace,
    list_traces,
    resolve_outcome,
)

# Named, tunable thresholds — not magic numbers buried in query logic.
ACTIVE_WINDOW = timedelta(hours=24)  # "active_businesses" in the founder summary
STALE_ACTIVITY_WINDOW = timedelta(days=7)  # "no_recent_activity" alert
RECENT_FAILURE_WINDOW = timedelta(hours=24)  # "ai_failures" alert


def _now() -> datetime:
    # Naive/UTC-implied, matching every other timestamp in this schema (DEC-032).
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _conversation_counts(db: Session) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Conversation.business_id, func.count().label("n")).group_by(Conversation.business_id)
    ).all()
    return {row.business_id: row.n for row in rows}


def _message_stats(db: Session, *, recent_failure_cutoff: datetime) -> dict[uuid.UUID, dict]:
    """One grouped query for every per-business message-derived metric this
    dashboard needs — outbound count (AI responses), failure counts
    (all-time and recent, for the ai_failures alert), and last
    inbound/outbound/any-direction timestamps (last activity)."""
    rows = db.execute(
        select(
            Message.business_id,
            func.count().filter(Message.direction == "outbound").label("ai_responses"),
            func.count().filter(Message.status == "failed").label("failed_responses"),
            func.count()
            .filter(Message.status == "failed", Message.created_at >= recent_failure_cutoff)
            .label("recent_failed_responses"),
            func.max(Message.created_at)
            .filter(Message.direction == "inbound")
            .label("last_inbound_at"),
            func.max(Message.created_at)
            .filter(Message.direction == "outbound")
            .label("last_outbound_at"),
            func.max(Message.created_at).label("last_activity_at"),
        ).group_by(Message.business_id)
    ).all()
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


def _response_time_seconds_by_business(db: Session) -> dict[uuid.UUID, float]:
    """Average seconds between an inbound message and the very next message
    in that same conversation, when that next message is outbound — the
    real "AI response time," computed in one window-function query rather
    than fetched into Python and paired up by hand (which wouldn't scale
    with message volume). `LAG` requires a subquery since you can't filter
    directly on a window function in the same SELECT it's defined in.
    """
    prev_created_at = func.lag(Message.created_at).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    prev_direction = func.lag(Message.direction).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    turns = select(
        Message.business_id.label("business_id"),
        Message.direction.label("direction"),
        Message.created_at.label("created_at"),
        prev_created_at.label("prev_created_at"),
        prev_direction.label("prev_direction"),
    ).subquery()

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


def _overall_response_time_seconds(db: Session) -> float | None:
    """Same computation as above, ungrouped — a genuine average across every
    qualifying turn platform-wide, not an average-of-per-business-averages
    (which would over-weight low-volume businesses)."""
    prev_created_at = func.lag(Message.created_at).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    prev_direction = func.lag(Message.direction).over(
        partition_by=Message.conversation_id, order_by=Message.created_at
    )
    turns = select(
        Message.direction.label("direction"),
        Message.created_at.label("created_at"),
        prev_created_at.label("prev_created_at"),
        prev_direction.label("prev_direction"),
    ).subquery()

    result = db.execute(
        select(func.avg(func.extract("epoch", turns.c.created_at - turns.c.prev_created_at))).where(
            turns.c.direction == "outbound", turns.c.prev_direction == "inbound"
        )
    ).scalar()
    return float(result) if result is not None else None


def _kb_stats(db: Session) -> dict[uuid.UUID, dict]:
    rows = db.execute(
        select(
            KbEntry.business_id,
            func.count().filter(KbEntry.status == "published").label("published_count"),
            func.count().filter(KbEntry.status == "draft").label("draft_count"),
            func.max(KbEntry.updated_at).label("last_updated_at"),
        ).group_by(KbEntry.business_id)
    ).all()
    return {
        row.business_id: {
            "published_count": row.published_count,
            "draft_count": row.draft_count,
            "last_updated_at": row.last_updated_at,
        }
        for row in rows
    }


def _businesses_with_stored_credential(db: Session) -> set[uuid.UUID]:
    return set(db.scalars(select(WhatsAppCredential.business_id)))


def _today_totals(db: Session, *, since: datetime) -> dict[str, int]:
    row = db.execute(
        select(
            func.count().label("messages_today"),
            func.count().filter(Message.direction == "outbound").label("ai_responses_today"),
            func.count().filter(Message.status == "failed").label("failed_responses_today"),
        ).where(Message.created_at >= since)
    ).one()
    return {
        "messages_today": row.messages_today,
        "ai_responses_today": row.ai_responses_today,
        "failed_responses_today": row.failed_responses_today,
    }


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _business_alerts(
    *,
    whatsapp_connected: bool,
    kb_published_count: int,
    recent_failed_responses: int,
    last_activity_at: datetime | None,
    now: datetime,
) -> list[str]:
    alerts: list[str] = []
    if not whatsapp_connected:
        alerts.append("whatsapp_disconnected")
    if kb_published_count == 0:
        alerts.append("missing_knowledge_base")
    if recent_failed_responses > 0:
        alerts.append("ai_failures")
    # Only flag staleness for a business that's actually supposed to be
    # receiving traffic — a brand-new, not-yet-connected business has no
    # activity by definition and that's not a problem, just early.
    if whatsapp_connected and (
        last_activity_at is None or now - last_activity_at > STALE_ACTIVITY_WINDOW
    ):
        alerts.append("no_recent_activity")
    return alerts


def get_founder_overview(db: Session) -> dict:
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    businesses = list(db.scalars(select(Business).order_by(Business.created_at.desc())))
    conversation_counts = _conversation_counts(db)
    message_stats = _message_stats(db, recent_failure_cutoff=now - RECENT_FAILURE_WINDOW)
    response_times = _response_time_seconds_by_business(db)
    kb_stats = _kb_stats(db)
    credentialed = _businesses_with_stored_credential(db)
    today = _today_totals(db, since=today_start)

    business_rows = []
    connected_count = 0
    active_count = 0
    for business in businesses:
        msg = message_stats.get(
            business.id,
            {
                "ai_responses": 0,
                "failed_responses": 0,
                "recent_failed_responses": 0,
                "last_inbound_at": None,
                "last_outbound_at": None,
                "last_activity_at": None,
            },
        )
        kb = kb_stats.get(
            business.id, {"published_count": 0, "draft_count": 0, "last_updated_at": None}
        )
        whatsapp_connected = business.whatsapp_connection_status == "connected"
        knowledge_base_ready = kb["published_count"] > 0

        if whatsapp_connected:
            connected_count += 1
        if msg["last_activity_at"] is not None and now - msg["last_activity_at"] <= ACTIVE_WINDOW:
            active_count += 1

        business_rows.append(
            {
                "id": str(business.id),
                "name": business.name,
                "created_at": _iso(business.created_at),
                "onboarding_status": business.onboarding_status,
                "onboarding_complete": knowledge_base_ready and whatsapp_connected,
                "whatsapp": {
                    "status": business.whatsapp_connection_status,
                    "display_phone_number": business.whatsapp_display_phone_number,
                    "credential_stored": business.id in credentialed,
                    "last_inbound_at": _iso(msg["last_inbound_at"]),
                    "last_outbound_at": _iso(msg["last_outbound_at"]),
                },
                "knowledge_base": {
                    "published_count": kb["published_count"],
                    "draft_count": kb["draft_count"],
                    "last_updated_at": _iso(kb["last_updated_at"]),
                },
                "ai_activity": {
                    "conversations": conversation_counts.get(business.id, 0),
                    "ai_responses": msg["ai_responses"],
                    "failed_responses": msg["failed_responses"],
                    "avg_response_time_seconds": response_times.get(business.id),
                },
                "last_activity_at": _iso(msg["last_activity_at"]),
                "alerts": _business_alerts(
                    whatsapp_connected=whatsapp_connected,
                    kb_published_count=kb["published_count"],
                    recent_failed_responses=msg["recent_failed_responses"],
                    last_activity_at=msg["last_activity_at"],
                    now=now,
                ),
            }
        )

    return {
        "summary": {
            "total_businesses": len(businesses),
            "connected_businesses": connected_count,
            "active_businesses": active_count,
            "messages_today": today["messages_today"],
            "ai_responses_today": today["ai_responses_today"],
            "failed_responses_today": today["failed_responses_today"],
            "avg_response_time_seconds": _overall_response_time_seconds(db),
        },
        "businesses": business_rows,
    }


def get_ai_metrics(db: Session) -> dict:
    """AI Employee observability for the Founder Ops dashboard (Sprint 76,
    Objective B) — aggregated from every `ExecutionTrace` row platform-wide.
    Two bulk queries (traces, then their result Messages), never one per
    trace — the same "fixed number of round trips" shape as
    get_founder_overview above, just aggregated in Python rather than SQL
    since grouping by values *inside* a JSONB array (proposed_tool_calls)
    doesn't fit a plain GROUP BY.
    """
    traces = list(db.scalars(select(ExecutionTrace)))
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
        # A proxy, not an exact count: app/ai/plan.py's clarification_hint
        # covers both "not ready yet" (missing details) and "governance
        # withheld this" — the two aren't distinguishable from the trace
        # alone without duplicating governance.py's policy table here. Good
        # enough for "how often did planning stop early", which is what
        # this dashboard tile actually needs.
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


def list_traces_for_dashboard(
    db: Session, *, business_id: uuid.UUID | None = None, limit: int = 50, offset: int = 0
) -> list[dict]:
    """Row summaries for the Conversation Replay list (Sprint 76, Objective
    C) — one bulk trace query, one bulk Message query, one bulk Business
    query, regardless of how many traces are returned."""
    traces = list_traces(db, business_id=business_id, limit=limit, offset=offset)
    if not traces:
        return []

    business_names = {
        business.id: business.name
        for business in db.scalars(
            select(Business).where(Business.id.in_({trace.business_id for trace in traces}))
        )
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
        rows.append(
            {
                "id": str(trace.id),
                "business_id": str(trace.business_id),
                "business_name": business_names.get(trace.business_id),
                "category": trace.category,
                "plan_step_count": len(trace.plan.get("steps", [])),
                "roles": [step["role"] for step in trace.plan.get("steps", []) if step.get("role")],
                "outcome": resolve_outcome(result_messages),
                "duration_ms": trace.duration_ms,
                "created_at": _iso(trace.created_at),
            }
        )
    return rows


def get_trace_detail(db: Session, trace_id: uuid.UUID) -> dict | None:
    """Full Conversation Replay detail (Sprint 76, Objective C): customer
    message -> execution plan -> employee sequence -> tool execution ->
    final response. Read-only, no editing — see app/services/
    execution_traces.py's docstring for why this is safe to derive purely
    by joining to the trace's current Messages rather than needing its own
    mutation path.
    """
    trace = get_trace(db, trace_id)
    if trace is None:
        return None

    business = db.get(Business, trace.business_id)
    trigger_message = (
        db.get(Message, trace.trigger_message_id) if trace.trigger_message_id else None
    )
    result_messages = get_result_messages(db, trace)

    return {
        "id": str(trace.id),
        "business_id": str(trace.business_id),
        "business_name": business.name if business else None,
        "conversation_id": str(trace.conversation_id),
        "category": trace.category,
        "customer_message": trigger_message.body if trigger_message else None,
        "plan": trace.plan,
        "proposed_tool_calls": trace.proposed_tool_calls,
        "result_messages": [
            {
                "id": str(message.id),
                "type": message.type,
                "body": message.body,
                "status": message.status,
                "ai_meta": message.ai_meta,
            }
            for message in result_messages
        ],
        "outcome": resolve_outcome(result_messages),
        "duration_ms": trace.duration_ms,
        "created_at": _iso(trace.created_at),
    }
