"""Customers API (/api/v1/customers) — Sprint 28 (DEC-031), manual
create/update/delete added Sprint 37.

Replaces the previously backend-less Customers page: a searchable, paginated
list, a detail view (customer + its lead, if any), and a timeline aggregating
message history with CRM (lead) activity. Every route sits behind
`get_current_principal` and is tenant-scoped, same as every other router.

POST/PATCH/DELETE (Sprint 37) let an owner manage customers who haven't
messaged in yet — e.g. a walk-in or phone booking. They only ever touch the
Customer row: no Lead, Conversation, or Message is created, and no WhatsApp
send is attempted (app/services/customers.py never imports anything from
app/services/messaging.py or app/ai/*).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenant import get_scoped, tenant_query
from app.models import Conversation, Customer, Lead
from app.services.customers import (
    CustomerAlreadyExistsError,
    CustomerNotFoundError,
    create_customer,
    delete_customer,
    update_customer,
)
from app.services.timeline import get_customer_timeline

router = APIRouter(prefix="/api/v1/customers", tags=["customers"])

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_TIMELINE_LIMIT = 30
MAX_TIMELINE_LIMIT = 100

# WhatsApp Cloud API phone number ids/E.164 numbers are well under this;
# generous ceiling for a manually-typed value, matches the wa_phone column.
MAX_PHONE_LENGTH = 32
MAX_NOTES_LENGTH = 4096


class CreateCustomerRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    wa_phone: str | None = Field(default=None, max_length=MAX_PHONE_LENGTH)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)


class UpdateCustomerRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    wa_phone: str | None = Field(default=None, max_length=MAX_PHONE_LENGTH)
    email: EmailStr | None = None
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LENGTH)


def _conversation_stats(
    db: Session, business_id: uuid.UUID, customer_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[int, datetime | None]]:
    """One row per customer: (conversation count, most recent last_message_at)."""
    if not customer_ids:
        return {}
    stmt = (
        select(
            Conversation.customer_id,
            func.count(Conversation.id),
            func.max(Conversation.last_message_at),
        )
        .where(Conversation.business_id == business_id, Conversation.customer_id.in_(customer_ids))
        .group_by(Conversation.customer_id)
    )
    return {row[0]: (row[1], row[2]) for row in db.execute(stmt).all()}


def _leads_by_customer(
    db: Session, business_id: uuid.UUID, customer_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Lead]:
    if not customer_ids:
        return {}
    rows = db.scalars(
        select(Lead).where(Lead.business_id == business_id, Lead.customer_id.in_(customer_ids))
    ).all()
    return {lead.customer_id: lead for lead in rows}


def _serialize_lead_summary(lead: Lead | None) -> dict | None:
    if lead is None:
        return None
    return {"id": str(lead.id), "stage": lead.stage}


def _serialize_lead_full(lead: Lead | None) -> dict | None:
    if lead is None:
        return None
    return {
        "id": str(lead.id),
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


def _serialize_customer_summary(
    customer: Customer,
    *,
    conversation_count: int,
    last_message_at: datetime | None,
    lead: Lead | None,
) -> dict:
    return {
        "id": str(customer.id),
        "display_name": customer.display_name,
        "wa_phone": customer.wa_phone,
        "email": customer.email,
        "notes": customer.notes,
        "created_at": customer.created_at.isoformat(),
        "conversation_count": conversation_count,
        "last_message_at": last_message_at.isoformat() if last_message_at else None,
        "lead": _serialize_lead_summary(lead),
    }


@router.get("")
def list_customers(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = tenant_query(Customer, principal.business_id)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Customer.display_name.ilike(like), Customer.wa_phone.ilike(like)))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by(Customer.created_at.desc()).limit(limit).offset(offset)
    customers = db.scalars(stmt).all()

    customer_ids = [c.id for c in customers]
    stats = _conversation_stats(db, principal.business_id, customer_ids)
    leads = _leads_by_customer(db, principal.business_id, customer_ids)

    data = [
        _serialize_customer_summary(
            c,
            conversation_count=stats.get(c.id, (0, None))[0],
            last_message_at=stats.get(c.id, (0, None))[1],
            lead=leads.get(c.id),
        )
        for c in customers
    ]
    return {"data": data, "meta": {"total": total, "limit": limit, "offset": offset}}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_customer_route(
    payload: CreateCustomerRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    display_name = payload.display_name.strip()
    if not display_name:
        raise HTTPException(status_code=422, detail="Name is required")
    wa_phone = payload.wa_phone.strip() if payload.wa_phone else None
    notes = payload.notes.strip() if payload.notes else None

    try:
        customer = create_customer(
            db,
            principal.business_id,
            display_name=display_name,
            wa_phone=wa_phone or None,
            email=payload.email,
            notes=notes or None,
        )
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    data = _serialize_customer_summary(
        customer, conversation_count=0, last_message_at=None, lead=None
    )
    return {"data": data}


@router.get("/{customer_id}")
def get_customer(
    customer_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    customer = get_scoped(db, Customer, principal.business_id, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    stats = _conversation_stats(db, principal.business_id, [customer.id])
    leads = _leads_by_customer(db, principal.business_id, [customer.id])
    count, last_message_at = stats.get(customer.id, (0, None))

    data = _serialize_customer_summary(
        customer, conversation_count=count, last_message_at=last_message_at, lead=None
    )
    data["lead"] = _serialize_lead_full(leads.get(customer.id))
    return {"data": data}


@router.get("/{customer_id}/timeline")
def get_customer_timeline_route(
    customer_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_TIMELINE_LIMIT, ge=1, le=MAX_TIMELINE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict:
    customer = get_scoped(db, Customer, principal.business_id, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    items, total = get_customer_timeline(
        db, principal.business_id, customer_id, limit=limit, offset=offset
    )
    return {"data": items, "meta": {"total": total, "limit": limit, "offset": offset}}


@router.patch("/{customer_id}")
def patch_customer(
    customer_id: uuid.UUID,
    payload: UpdateCustomerRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")

    if "display_name" in updates:
        name = (updates["display_name"] or "").strip()
        if not name:
            raise HTTPException(status_code=422, detail="Name cannot be blank")
        updates["display_name"] = name
    if "wa_phone" in updates and updates["wa_phone"]:
        updates["wa_phone"] = updates["wa_phone"].strip() or None
    if "notes" in updates and updates["notes"]:
        updates["notes"] = updates["notes"].strip() or None
    if "email" in updates and updates["email"] is not None:
        updates["email"] = str(updates["email"])

    try:
        customer = update_customer(db, principal.business_id, customer_id, updates)
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except CustomerAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    stats = _conversation_stats(db, principal.business_id, [customer.id])
    leads = _leads_by_customer(db, principal.business_id, [customer.id])
    count, last_message_at = stats.get(customer.id, (0, None))
    data = _serialize_customer_summary(
        customer, conversation_count=count, last_message_at=last_message_at, lead=None
    )
    data["lead"] = _serialize_lead_full(leads.get(customer.id))
    return {"data": data}


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_customer(
    customer_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    if not delete_customer(db, principal.business_id, customer_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
