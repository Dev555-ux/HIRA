"""Leads API (/api/v1/leads) — the CRM pipeline (Sprint 28, DEC-031).

One Lead per (business, customer). `stage` is one of the seven pipeline
stages below — validated here via a Pydantic `Literal`, but stored as a plain
string with no DB-level CHECK constraint, matching every other status field
in this schema (Message.status, Conversation.status). Every route sits behind
`get_current_principal` and is tenant-scoped via `tenant_query`/`get_scoped`,
same as dashboard.py/knowledge_base.py/conversations.py.

POST /api/v1/leads (Sprint 38) creates a lead without an existing customer
already selected — `customer_id` is now optional; when omitted, the customer
is resolved by phone, then email, then created from the submitted contact
fields (app/services/customers.py's resolve_or_create_customer). This route
is the only thing that changed for manual lead creation — create_lead()
itself (app/services/leads.py) is untouched and still requires a real,
already-known customer_id, since app/ai/lead_tools.py calls it positionally
with one during live WhatsApp conversations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenant import get_scoped
from app.models import Customer, Lead
from app.services.customers import (
    CustomerAlreadyExistsError,
    CustomerNotFoundError,
    MissingCustomerInfoError,
    resolve_or_create_customer,
)
from app.services.leads import InvalidAssigneeError, LeadAlreadyExistsError, LeadNotFoundError
from app.services.leads import CustomerNotFoundError as LeadServiceCustomerNotFoundError
from app.services.leads import create_lead, delete_lead, update_lead

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])

LeadStage = Literal["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
MAX_PHONE_LENGTH = 32
# source matches Lead.source's own String(64) column (app/models.py) —
# without this, an oversized value fails at commit with a raw DB error
# instead of a clean 422. notes has no DB-side bound (Lead.notes is Text),
# matching customers.py's own MAX_NOTES_LENGTH convention for the same kind
# of field.
MAX_SOURCE_LENGTH = 64
MAX_NOTES_LENGTH = 4096


class CreateLeadRequest(BaseModel):
    # Either customer_id (an already-known customer — e.g. from the customer
    # detail page), or enough contact info to find/create one. display_name
    # is only actually required when no customer_id/phone-match/email-match
    # resolves to an existing customer — enforced in resolve_or_create_customer,
    # not here, since it depends on what else was found.
    customer_id: uuid.UUID | None = None
    display_name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    wa_phone: str | None = Field(default=None, max_length=MAX_PHONE_LENGTH)
    email: EmailStr | None = None
    stage: LeadStage = "new"
    source: str | None = Field(default=None, max_length=MAX_SOURCE_LENGTH)
    estimated_value: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)
    next_follow_up_at: datetime | None = None
    assigned_to: uuid.UUID | None = None


class UpdateLeadRequest(BaseModel):
    stage: LeadStage | None = None
    source: str | None = Field(default=None, max_length=MAX_SOURCE_LENGTH)
    estimated_value: float | None = Field(default=None, ge=0)
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)
    next_follow_up_at: datetime | None = None
    assigned_to: uuid.UUID | None = None


def _serialize_lead(lead: Lead, customer: Customer) -> dict:
    return {
        "id": str(lead.id),
        "customer": {
            "id": str(customer.id),
            "display_name": customer.display_name,
            "company": customer.company,
            "wa_phone": customer.wa_phone,
            "email": customer.email,
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
        customer = resolve_or_create_customer(
            db,
            principal.business_id,
            customer_id=payload.customer_id,
            wa_phone=payload.wa_phone.strip() if payload.wa_phone else None,
            email=payload.email,
            display_name=payload.display_name,
            company=payload.company.strip() if payload.company else None,
        )
    except CustomerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        ) from exc
    except MissingCustomerInfoError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    try:
        lead = create_lead(
            db,
            principal.business_id,
            customer.id,
            stage=payload.stage,
            source=payload.source,
            estimated_value=payload.estimated_value,
            notes=payload.notes,
            next_follow_up_at=payload.next_follow_up_at,
            assigned_to=payload.assigned_to,
        )
    except LeadServiceCustomerNotFoundError as exc:
        # Defensive only — `customer` above was just resolved/created for
        # this exact business_id, so create_lead's own existence check can't
        # actually fail here. Mapped the same way as the check above in case
        # that invariant is ever broken by a future change.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        ) from exc
    except LeadAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A lead already exists for this customer"
        ) from exc
    except InvalidAssigneeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

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
