"""Analytics API (/api/v1/analytics) — the per-business dashboard (Analytics
Phase 1). One endpoint, tenant-scoped via `get_current_principal` like every
other route in dashboard.py/leads.py/etc. — deliberately not built on
`get_founder_principal`; there is no cross-tenant view here.

Every figure is computed by app/services/analytics.py, the same
business_id-parameterized module the Founder Operations Dashboard uses
(app/services/founder_ops.py). This router only resolves the `range` query
param into a since/until window, fetches the Business row (not itself
business_id-scoped — it *is* the tenant, so `tenant_query` doesn't apply;
every other query below goes through the service's business_id filtering
instead), and assembles the service's return values into one response. It
adds no aggregation SQL of its own.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.models import Appointment, Business, Conversation, Lead
from app.services.analytics import (
    ai_impact,
    ai_metrics,
    business_alerts,
    conversation_counts,
    iso,
    kb_stats,
    message_stats,
    overall_response_time_seconds,
    status_breakdown,
    today_totals,
    trends,
)

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

AnalyticsRange = Literal["7d", "30d", "90d"]
RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90}

# Same threshold founder_ops.py uses for "no_recent_activity" — kept in sync
# manually since it's a business_alerts() call arg, not something the shared
# service can default on its own (see app/services/analytics.py).
STALE_ACTIVITY_WINDOW = timedelta(days=7)
RECENT_FAILURE_WINDOW = timedelta(hours=24)


def _now() -> datetime:
    # Naive/UTC-implied, matching every timestamp in this schema (DEC-032).
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/dashboard")
def get_dashboard(
    range_: AnalyticsRange = Query(default="30d", alias="range"),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    business_id = principal.business_id
    now = _now()
    since = now - timedelta(days=RANGE_DAYS[range_])
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    business = db.get(Business, business_id)

    msg = message_stats(
        db, recent_failure_cutoff=now - RECENT_FAILURE_WINDOW, business_id=business_id
    ).get(
        business_id,
        {
            "ai_responses": 0,
            "failed_responses": 0,
            "recent_failed_responses": 0,
            "last_inbound_at": None,
            "last_outbound_at": None,
            "last_activity_at": None,
        },
    )
    kb = kb_stats(db, business_id=business_id).get(
        business_id, {"published_count": 0, "draft_count": 0, "last_updated_at": None}
    )
    whatsapp_connected = business.whatsapp_connection_status == "connected"
    today = today_totals(db, since=today_start, business_id=business_id)

    overview = {
        "total_conversations": conversation_counts(db, business_id=business_id).get(business_id, 0),
        "messages_today": today["messages_today"],
        "ai_responses_today": today["ai_responses_today"],
        "failed_responses_today": today["failed_responses_today"],
        "avg_response_time_seconds": overall_response_time_seconds(db, business_id=business_id),
    }

    business_health = {
        "onboarding_status": business.onboarding_status,
        "trial_ends_at": iso(business.trial_ends_at),
        "created_at": iso(business.created_at),
        "whatsapp": {
            "status": business.whatsapp_connection_status,
            "display_phone_number": business.whatsapp_display_phone_number,
        },
        "knowledge_base": {
            "published_count": kb["published_count"],
            "draft_count": kb["draft_count"],
            "last_updated_at": iso(kb["last_updated_at"]),
        },
        "alerts": business_alerts(
            whatsapp_connected=whatsapp_connected,
            kb_published_count=kb["published_count"],
            recent_failed_responses=msg["recent_failed_responses"],
            last_activity_at=msg["last_activity_at"],
            now=now,
            stale_activity_window=STALE_ACTIVITY_WINDOW,
        ),
        "conversations_by_status": status_breakdown(
            db, Conversation, Conversation.status, business_id
        ),
        "leads_by_stage": status_breakdown(db, Lead, Lead.stage, business_id),
        "leads_by_source": status_breakdown(db, Lead, Lead.source, business_id),
        "appointments_by_status": status_breakdown(
            db, Appointment, Appointment.status, business_id
        ),
    }

    return {
        "range": range_,
        "overview": overview,
        "trends": trends(db, business_id, since=since, until=now),
        "ai_impact": ai_impact(db, business_id, since=since, until=now),
        "ai_performance": ai_metrics(db, business_id=business_id),
        "business_health": business_health,
    }
