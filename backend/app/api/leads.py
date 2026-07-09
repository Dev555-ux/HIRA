"""Leads API (/api/v1/leads) — the CRM pipeline (Sprint 28, DEC-031).

One Lead per (business, customer). `stage` is one of the seven pipeline
stages below — validated here via a Pydantic `Literal`, but stored as a plain
string with no DB-level CHECK constraint, matching every other status field
in this schema (Message.status, Conversation.status). Every route sits behind
`get_current_principal` and is tenant-scoped via `tenant_query`/`get_scoped`,
same as dashboard.py/knowledge_base.py/conversations.py.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenant import get_scoped
from app.models import Customer, Lead
from app.services.leads import (
    CustomerNotFoundError,
    InvalidAssigneeError,
    LeadAlreadyExistsError,
    LeadNotFoundError,
    create_lead,
    delete_lead,
    update_lead,
)

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

LeadStage = Literal["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class CreateLeadRequest(BaseModel):
    customer_id: uuid.UUID
    stage: LeadStage = "new"
    source: str | None = None
    estimated_value: float | None = None
    notes: str | None = None
    next_follow_up_at: datetime | None = None
    assigned_to: uuid.UUID | None = None


class UpdateLeadRequest(BaseModel):
    stage: LeadStage | None = None
    source: str | None = None
    estimated_value: float | None = None
    notes: str | None = None
    next_follow_up_at: datetime | None = None
    assigned_to: uuid.UUID | None = None


def _serialize_lead(lead: Lead, customer: Customer) -> dict:
    return {
        "id": str(lead.id),
        "customer": {
            "id": str(customer.id),
            "display_name": customer.display_name,
            "wa_phone": customer.wa_phone,
        },
        "stage": lead.stage,
        "source": lead.source,
        "estimated_value": (
            float(lead.estimated_value) if lead.estimated_value is not None else None
        ),
        "notes": lead.notes,
        "next_follow_up_at": (
            lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None
        ),
        "assigned_to": str(lead.assigned_to) if lead.assigned_to else None,
        "created_at": lead.created_at.isoformat(),
        "updated_at": lead.updated_at.isoformat(),
    }


@router.get("")
def list_leads(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    stage: LeadStage | None = Query(default=None),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = (
        select(Lead, Customer)
        .join(Customer, Customer.id == Lead.customer_id)
        .where(Lead.business_id == principal.business_id)
    )
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Customer.display_name.ilike(like), Customer.wa_phone.ilike(like)))
    if stage:
        stmt = stmt.where(Lead.stage == stage)

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Lead.updated_at.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).all()

    return {
        "data": [_serialize_lead(lead, customer) for lead, customer in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_lead_route(
    payload: CreateLeadRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    try:
        lead = create_lead(
            db,
            principal.business_id,
            payload.customer_id,
            stage=payload.stage,
            source=payload.source,
            estimated_value=payload.estimated_value,
            notes=payload.notes,
            next_follow_up_at=payload.next_follow_up_at,
            assigned_to=payload.assigned_to,
        )
    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        ) from exc
    except LeadAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A lead already exists for this customer"
        ) from exc
    except InvalidAssigneeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    customer = db.get(Customer, lead.customer_id)
    return {"data": _serialize_lead(lead, customer)}


@router.get("/{lead_id}")
def get_lead(
    lead_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    lead = get_scoped(db, Lead, principal.business_id, lead_id)
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    customer = db.get(Customer, lead.customer_id)
    return {"data": _serialize_lead(lead, customer)}


@router.patch("/{lead_id}")
def patch_lead(
    lead_id: uuid.UUID,
    payload: UpdateLeadRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")

    try:
        lead = update_lead(db, principal.business_id, lead_id, updates)
    except LeadNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except InvalidAssigneeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    customer = db.get(Customer, lead.customer_id)
    return {"data": _serialize_lead(lead, customer)}


@router.delete("/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_lead(
    lead_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    if not delete_lead(db, principal.business_id, lead_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
