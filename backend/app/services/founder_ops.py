"""Founder Operations Dashboard aggregates (Sprint 73) — a deliberately
cross-tenant, read-only view for `app/api/founder_ops.py`. Every query here
is grouped by `business_id` in bulk (never a per-business loop), so the cost
of this dashboard scales with the number of *query round trips* (fixed,
small), not the number of businesses — the "suitable for future growth"
requirement this sprint asked for.

The actual aggregation queries live in `app/services/analytics.py`, shared
with the per-business Analytics page (`app/api/analytics.py`) — every
function there takes an optional `business_id`; this module always calls
them with none, for the cross-tenant view. Kept as a separate module (not
merged into analytics.py) because everything below it — the founder-only
public functions, the Conversation Replay trace helpers — stays behind
`get_founder_principal`, a different gate than the tenant-scoped Analytics
endpoint.

This intentionally does not use `app/db/tenant.py`'s `tenant_query`/
`get_scoped` — both raise if you don't pass a `business_id`, which is the
whole point here. This module is the one deliberate, audited hole in an
otherwise tenant-scoped codebase; see `get_founder_principal` in
app/auth/dependencies.py for how access to it is gated.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, Message
from app.services.analytics import (
    ai_metrics as _ai_metrics,
    business_alerts,
    businesses_with_stored_credential,
    conversation_counts,
    iso,
    kb_stats,
    message_stats,
    overall_response_time_seconds,
    response_time_seconds_by_business,
    today_totals,
)
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


def get_founder_overview(db: Session) -> dict:
    now = _now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    businesses = list(db.scalars(select(Business).order_by(Business.created_at.desc())))
    conv_counts = conversation_counts(db)
    msg_stats = message_stats(db, recent_failure_cutoff=now - RECENT_FAILURE_WINDOW)
    response_times = response_time_seconds_by_business(db)
    kb_by_business = kb_stats(db)
    credentialed = businesses_with_stored_credential(db)
    today = today_totals(db, since=today_start)

    business_rows = []
    connected_count = 0
    active_count = 0
    for business in businesses:
        msg = msg_stats.get(
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
        kb = kb_by_business.get(
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
                "created_at": iso(business.created_at),
                "onboarding_status": business.onboarding_status,
                "onboarding_complete": knowledge_base_ready and whatsapp_connected,
                "whatsapp": {
                    "status": business.whatsapp_connection_status,
                    "display_phone_number": business.whatsapp_display_phone_number,
                    "credential_stored": business.id in credentialed,
                    "last_inbound_at": iso(msg["last_inbound_at"]),
                    "last_outbound_at": iso(msg["last_outbound_at"]),
                },
                "knowledge_base": {
                    "published_count": kb["published_count"],
                    "draft_count": kb["draft_count"],
                    "last_updated_at": iso(kb["last_updated_at"]),
                },
                "ai_activity": {
                    "conversations": conv_counts.get(business.id, 0),
                    "ai_responses": msg["ai_responses"],
                    "failed_responses": msg["failed_responses"],
                    "avg_response_time_seconds": response_times.get(business.id),
                },
                "last_activity_at": iso(msg["last_activity_at"]),
                "alerts": business_alerts(
                    whatsapp_connected=whatsapp_connected,
                    kb_published_count=kb["published_count"],
                    recent_failed_responses=msg["recent_failed_responses"],
                    last_activity_at=msg["last_activity_at"],
                    now=now,
                    stale_activity_window=STALE_ACTIVITY_WINDOW,
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
            "avg_response_time_seconds": overall_response_time_seconds(db),
        },
        "businesses": business_rows,
    }


def get_ai_metrics(db: Session) -> dict:
    """AI Employee observability for the Founder Ops dashboard (Sprint 76,
    Objective B): employee utilisation, most-used employee/tools, failed
    tool executions, governance blocks, and average plan length/execution
    time — aggregated across every business's execution traces. Thin
    wrapper over `app/services/analytics.py::ai_metrics` (business_id=None,
    the cross-tenant case) — see that function's docstring for how each
    figure is computed.
    """
    return _ai_metrics(db)


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
                "created_at": iso(trace.created_at),
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
        "created_at": iso(trace.created_at),
    }
