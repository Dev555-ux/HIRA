"""Escalation queue API (/api/v1/escalations) — the workspace for conversations
a human needs to handle (low-confidence AI replies, explicit customer
requests, delivery failures — see Escalation.reason).

Every route sits behind `get_current_principal` and every query is
tenant-scoped via `get_scoped`/an explicit `business_id` filter, same as
conversations.py/dashboard.py — a business can only ever see or act on its
own escalations.

Assignment is a self-claim, not an assign-to-others picker (Sprint 69) —
there's no team roster/user-picker UI yet, so `POST /{id}/assign` always
assigns to the calling principal. `POST /{id}/resolve` is the terminal
action; there is no reopen endpoint (out of scope for this sprint — see
DEC-040).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenant import get_scoped
from app.models import Conversation, Customer, Escalation, User

router = APIRouter(prefix="/api/v1/escalations", tags=["escalations"])

StatusFilter = Literal["open", "resolved"]
AssignedFilter = Literal["mine", "unassigned"]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_emails(db: Session, user_ids: set[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not user_ids:
        return {}
    rows = db.execute(select(User.id, User.email).where(User.id.in_(user_ids))).all()
    return {row.id: row.email for row in rows}


def _serialize(
    escalation: Escalation,
    conversation: Conversation,
    customer: Customer,
    emails: dict[uuid.UUID, str],
) -> dict:
    return {
        "id": str(escalation.id),
        "reason": escalation.reason,
        "status": escalation.status,
        "assigned_to": (
            {"id": str(escalation.assigned_to), "email": emails.get(escalation.assigned_to)}
            if escalation.assigned_to
            else None
        ),
        "resolved_by": (
            {"id": str(escalation.resolved_by), "email": emails.get(escalation.resolved_by)}
            if escalation.resolved_by
            else None
        ),
        "resolved_at": escalation.resolved_at.isoformat() if escalation.resolved_at else None,
        "created_at": escalation.created_at.isoformat(),
        "conversation": {
            "id": str(conversation.id),
            "customer": {
                "id": str(customer.id),
                "display_name": customer.display_name,
                "wa_phone": customer.wa_phone,
            },
        },
    }


@router.get("")
def list_escalations(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    status_filter: StatusFilter | None = Query(default=None, alias="status"),
    assigned: AssignedFilter | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = (
        select(Escalation, Conversation, Customer)
        .join(Conversation, Conversation.id == Escalation.conversation_id)
        .join(Customer, Customer.id == Conversation.customer_id)
        .where(Escalation.business_id == principal.business_id)
    )

    if status_filter is not None:
        stmt = stmt.where(Escalation.status == status_filter)
    if assigned == "mine":
        stmt = stmt.where(Escalation.assigned_to == principal.user_id)
    elif assigned == "unassigned":
        stmt = stmt.where(Escalation.assigned_to.is_(None))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    stmt = stmt.order_by(Escalation.created_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).all()

    user_ids = {esc.assigned_to for esc, _, _ in rows if esc.assigned_to} | {
        esc.resolved_by for esc, _, _ in rows if esc.resolved_by
    }
    emails = _user_emails(db, user_ids)

    return {
        "data": [_serialize(esc, conv, cust, emails) for esc, conv, cust in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("/{escalation_id}/assign")
def assign_escalation(
    escalation_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    escalation = get_scoped(db, Escalation, principal.business_id, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    # Conditional UPDATE, not a load-then-write: two requests racing to claim
    # the same escalation serialize on Postgres's row-level lock here, so only
    # one can ever win. The WHERE clause also re-asserts tenant scoping
    # (get_scoped above already confirmed it, but the mutation stays
    # self-contained rather than trusting a moment-old read) and allows a
    # no-op re-claim by whoever already holds it.
    claimed = db.execute(
        update(Escalation)
        .where(
            Escalation.id == escalation_id,
            Escalation.business_id == principal.business_id,
            (Escalation.assigned_to.is_(None)) | (Escalation.assigned_to == principal.user_id),
        )
        .values(assigned_to=principal.user_id)
    ).rowcount
    db.commit()
    if claimed == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This escalation is already assigned to someone else.",
        )

    db.refresh(escalation)
    conversation = db.get(Conversation, escalation.conversation_id)
    customer = db.get(Customer, conversation.customer_id)
    emails = _user_emails(db, {escalation.assigned_to})
    return {"data": _serialize(escalation, conversation, customer, emails)}


@router.post("/{escalation_id}/unassign")
def unassign_escalation(
    escalation_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    escalation = get_scoped(db, Escalation, principal.business_id, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if escalation.assigned_to != principal.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the user who claimed this escalation can unassign it.",
        )

    escalation.assigned_to = None
    db.commit()
    db.refresh(escalation)
    conversation = db.get(Conversation, escalation.conversation_id)
    customer = db.get(Customer, conversation.customer_id)
    emails = _user_emails(db, {escalation.resolved_by} if escalation.resolved_by else set())
    return {"data": _serialize(escalation, conversation, customer, emails)}


@router.post("/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    escalation = get_scoped(db, Escalation, principal.business_id, escalation_id)
    if escalation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    escalation.status = "resolved"
    escalation.resolved_by = principal.user_id
    escalation.resolved_at = _now()

    conversation = db.get(Conversation, escalation.conversation_id)
    # Resolving is what actually clears "escalated" — without this, the
    # conversation stays permanently stuck out of the Inbox's Open filter and
    # permanently stuck in its Escalated filter, even though the escalation
    # itself is now resolved (release-review finding).
    if conversation is not None and conversation.status == "escalated":
        conversation.status = "active"

    db.commit()
    db.refresh(escalation)
    customer = db.get(Customer, conversation.customer_id)
    emails = _user_emails(
        db,
        {escalation.resolved_by} | ({escalation.assigned_to} if escalation.assigned_to else set()),
    )
    return {"data": _serialize(escalation, conversation, customer, emails)}
