"""Founder Operations Dashboard API (/api/v1/founder) — Sprint 73.

Internal-only, read-only, cross-tenant. Every route sits behind
`get_founder_principal` (app/auth/dependencies.py), an allowlist of Clerk
user ids — deliberately NOT `get_current_principal`, since this view spans
every business rather than scoping to the caller's own one. A non-founder
caller (any real customer, i.e. every other authenticated user) gets a 404,
matching this API's existing convention of not confirming a resource exists
to someone not entitled to see it.

No mutation endpoints exist here on purpose — "read-only, no destructive
actions" was an explicit requirement, and there was no request needing one.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_founder_principal
from app.db.session import get_db
from app.services.founder_ops import (
    get_ai_metrics,
    get_founder_overview,
    get_trace_detail,
    list_traces_for_dashboard,
)

router = APIRouter(prefix="/api/v1/founder", tags=["founder-ops"])

DEFAULT_TRACE_LIMIT = 50
MAX_TRACE_LIMIT = 200


@router.get("/overview")
def get_overview(
    _founder_clerk_user_id: str = Depends(get_founder_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Everything the Founder Operations Dashboard needs in one response —
    the summary tiles plus a full per-business breakdown (WhatsApp health,
    Knowledge Base status, AI activity, and derived alerts). One request
    covers Objectives 1-6 from Sprint 73's brief; see app/services/
    founder_ops.py for how each figure is computed and documentation/API.md
    for the response shape.
    """
    return {"data": get_founder_overview(db)}


@router.get("/ai-metrics")
def get_ai_metrics_endpoint(
    _founder_clerk_user_id: str = Depends(get_founder_principal),
    db: Session = Depends(get_db),
) -> dict:
    """AI Employee observability (Sprint 76, Objective B): employee
    utilisation, most-used employee/tools, failed tool executions,
    governance blocks, and average plan length/execution time — aggregated
    across every business's execution traces. See app/services/
    founder_ops.py::get_ai_metrics for how each figure is computed.
    """
    return {"data": get_ai_metrics(db)}


@router.get("/traces")
def list_traces_endpoint(
    business_id: uuid.UUID | None = Query(default=None),
    limit: int = Query(default=DEFAULT_TRACE_LIMIT, ge=1, le=MAX_TRACE_LIMIT),
    offset: int = Query(default=0, ge=0),
    _founder_clerk_user_id: str = Depends(get_founder_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Conversation Replay list (Sprint 76, Objective C) — one row summary
    per execution trace, newest first, optionally filtered to one business.
    """
    return {
        "data": list_traces_for_dashboard(db, business_id=business_id, limit=limit, offset=offset)
    }


@router.get("/traces/{trace_id}")
def get_trace_detail_endpoint(
    trace_id: uuid.UUID,
    _founder_clerk_user_id: str = Depends(get_founder_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Conversation Replay detail (Sprint 76, Objective C): customer message
    -> execution plan -> employee sequence -> tool execution -> final
    response, for one turn. Read-only.
    """
    detail = get_trace_detail(db, trace_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"data": detail}
