"""Appointments API (/api/v1/appointments) — Sprint 29 (DEC-032).

Booking/rescheduling/cancelling always goes through `AppointmentService`
(`app/calendar/factory.py::get_appointment_service`), which writes to the
connected Google Calendar first — there is no "local-only" appointment path,
matching `AppointmentService`'s existing "external calendar is the source of
truth" design (DEC-028). A business with no connected calendar gets `409`
(`CalendarNotConnectedError`) on every write here.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.calendar import map_calendar_error
from app.auth.dependencies import Principal, get_current_principal
from app.calendar.factory import get_appointment_service
from app.calendar.providers.base import CalendarError
from app.core.time import to_iso_utc
from app.db.session import get_db
from app.db.tenant import get_scoped, tenant_query
from app.models import Appointment, Customer

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])

# Sprint 36: same guard-rail rationale as dashboard.py's /pending — a cap
# against a truly unbounded scan, defaulted high enough that today's
# "see every appointment in range" behavior is unchanged for any realistic
# business.
DEFAULT_APPOINTMENT_LIMIT = 200
MAX_APPOINTMENT_LIMIT = 200
# summary isn't persisted locally (Appointment has no such column — it's
# forwarded straight to the Google Calendar event title), so this is a
# sensible calendar-event-title-sized bound rather than a DB-column match.
MAX_SUMMARY_LENGTH = 255


class CreateAppointmentRequest(BaseModel):
    customer_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    summary: str = Field(max_length=MAX_SUMMARY_LENGTH)
    conversation_id: uuid.UUID | None = None


class RescheduleAppointmentRequest(BaseModel):
    starts_at: datetime
    ends_at: datetime


def _serialize(appointment: Appointment, customer: Customer | None) -> dict:
    return {
        "id": str(appointment.id),
        "customer": (
            {
                "id": str(customer.id),
                "display_name": customer.display_name,
                "wa_phone": customer.wa_phone,
            }
            if customer is not None
            else None
        ),
        "conversation_id": (
            str(appointment.conversation_id) if appointment.conversation_id else None
        ),
        "starts_at": to_iso_utc(appointment.starts_at),
        "ends_at": to_iso_utc(appointment.ends_at),
        "status": appointment.status,
        "created_at": to_iso_utc(appointment.created_at),
        "updated_at": to_iso_utc(appointment.updated_at),
    }


def _customers_by_id(db: Session, customer_ids: list[uuid.UUID]) -> dict[uuid.UUID, Customer]:
    if not customer_ids:
        return {}
    rows = db.scalars(select(Customer).where(Customer.id.in_(customer_ids))).all()
    return {c.id: c for c in rows}


@router.get("")
def list_appointments(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    limit: int = Query(default=DEFAULT_APPOINTMENT_LIMIT, ge=1, le=MAX_APPOINTMENT_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict:
    base_stmt = tenant_query(Appointment, principal.business_id)
    if from_ is not None:
        base_stmt = base_stmt.where(Appointment.starts_at >= from_)
    if to is not None:
        base_stmt = base_stmt.where(Appointment.starts_at <= to)
    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    stmt = base_stmt.order_by(Appointment.starts_at).limit(limit).offset(offset)
    rows = db.scalars(stmt).all()

    customers = _customers_by_id(db, [a.customer_id for a in rows])
    return {
        "data": [_serialize(a, customers.get(a.customer_id)) for a in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: CreateAppointmentRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    customer = get_scoped(db, Customer, principal.business_id, payload.customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")

    try:
        appointment_service = get_appointment_service(db, principal.business_id)
        appointment = appointment_service.book_appointment(
            customer_id=payload.customer_id,
            conversation_id=payload.conversation_id,
            starts_at=payload.starts_at,
            ends_at=payload.ends_at,
            summary=payload.summary,
        )
    except CalendarError as exc:
        raise map_calendar_error(exc) from exc

    return {"data": _serialize(appointment, customer)}


@router.get("/{appointment_id}")
def get_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    appointment = get_scoped(db, Appointment, principal.business_id, appointment_id)
    if appointment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    customer = db.get(Customer, appointment.customer_id)
    return {"data": _serialize(appointment, customer)}


@router.post("/{appointment_id}/reschedule")
def reschedule_appointment(
    appointment_id: uuid.UUID,
    payload: RescheduleAppointmentRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    if payload.ends_at <= payload.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")

    try:
        appointment_service = get_appointment_service(db, principal.business_id)
        appointment = appointment_service.reschedule_appointment(
            appointment_id=appointment_id,
            new_starts_at=payload.starts_at,
            new_ends_at=payload.ends_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except CalendarError as exc:
        raise map_calendar_error(exc) from exc

    customer = db.get(Customer, appointment.customer_id)
    return {"data": _serialize(appointment, customer)}


@router.post("/{appointment_id}/cancel")
def cancel_appointment(
    appointment_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    try:
        appointment_service = get_appointment_service(db, principal.business_id)
        appointment = appointment_service.cancel_appointment(appointment_id=appointment_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except CalendarError as exc:
        raise map_calendar_error(exc) from exc

    customer = db.get(Customer, appointment.customer_id)
    return {"data": _serialize(appointment, customer)}
