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
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.calendar import map_calendar_error
from app.auth.dependencies import Principal, get_current_principal
from app.calendar.factory import get_appointment_service
from app.calendar.providers.base import CalendarError
from app.db.session import get_db
from app.db.tenant import get_scoped, tenant_query
from app.models import Appointment, Customer

router = APIRouter(prefix="/api/v1/appointments", tags=["appointments"])


class CreateAppointmentRequest(BaseModel):
    customer_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    summary: str
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
        "starts_at": appointment.starts_at.isoformat(),
        "ends_at": appointment.ends_at.isoformat(),
        "status": appointment.status,
        "created_at": appointment.created_at.isoformat(),
        "updated_at": appointment.updated_at.isoformat(),
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
) -> dict:
    stmt = tenant_query(Appointment, principal.business_id).order_by(Appointment.starts_at)
    if from_ is not None:
        stmt = stmt.where(Appointment.starts_at >= from_)
    if to is not None:
        stmt = stmt.where(Appointment.starts_at <= to)
    rows = db.scalars(stmt).all()

    customers = _customers_by_id(db, [a.customer_id for a in rows])
    return {"data": [_serialize(a, customers.get(a.customer_id)) for a in rows]}


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
