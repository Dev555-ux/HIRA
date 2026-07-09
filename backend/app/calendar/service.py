"""Provider-agnostic appointment booking/rescheduling/cancelling.

Wraps a `CalendarProvider` (app/calendar/providers/) and the `Appointment`
table. Contains no vendor-specific logic — every call that actually talks to
a calendar API happens behind the CalendarProvider interface, so this class
never imports or knows about a specific vendor.

The provider is injected rather than resolved from stored credentials here on
purpose: credential resolution (decrypting a business's stored OAuth token,
choosing which vendor class to build) is a separate concern — deferred to
app/calendar/credentials.py, not yet built — so this service stays fully
testable against `MockCalendarProvider` with no database-backed credential
lookup required.

External calendar is the source of truth for the event; Postgres is the
source of truth for the appointment's link to a Customer/Conversation. On a
provider failure (e.g. CalendarConflictError), nothing is written to the
Appointment table — the exception simply propagates to the caller.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.calendar.providers.base import (
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarProvider,
    TimeSlot,
)
from app.calendar.working_hours import filter_by_working_hours
from app.db.tenant import get_scoped
from app.models import Appointment


class AppointmentService:
    def __init__(
        self,
        db: Session,
        business_id: uuid.UUID,
        provider: CalendarProvider,
        calendar_id: str,
        *,
        timezone: str = "UTC",
        working_hours: dict | None = None,
    ):
        self._db = db
        self._business_id = business_id
        self._provider = provider
        self._calendar_id = calendar_id
        self._timezone = timezone
        self._working_hours = working_hours

    def list_availability(self, *, starts_at: datetime, ends_at: datetime) -> list[TimeSlot]:
        """Free slots within [starts_at, ends_at], clipped to the business's
        working hours (see DEC-032) if configured — untouched if not."""
        slots = self._provider.get_availability(
            calendar_id=self._calendar_id,
            window=TimeSlot(starts_at=starts_at, ends_at=ends_at),
        )
        return filter_by_working_hours(
            slots, working_hours=self._working_hours, timezone=self._timezone
        )

    def book_appointment(
        self,
        *,
        customer_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        starts_at: datetime,
        ends_at: datetime,
        summary: str,
    ) -> Appointment:
        """Create the event on the calendar, then persist the Appointment row.

        Raises whatever the provider raises (e.g. CalendarConflictError) if
        the event can't be created — no Appointment row is written in that case.
        """
        event = self._provider.create_event(
            calendar_id=self._calendar_id,
            draft=CalendarEventDraft(starts_at=starts_at, ends_at=ends_at, summary=summary),
        )
        appointment = Appointment(
            business_id=self._business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            google_event_id=event.provider_event_id,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            status="booked",
        )
        self._db.add(appointment)
        self._db.commit()
        self._db.refresh(appointment)
        return appointment

    def reschedule_appointment(
        self,
        *,
        appointment_id: uuid.UUID,
        new_starts_at: datetime,
        new_ends_at: datetime,
    ) -> Appointment:
        appointment = get_scoped(self._db, Appointment, self._business_id, appointment_id)
        if appointment is None:
            raise ValueError("Appointment not found for this business")

        self._provider.update_event(
            calendar_id=self._calendar_id,
            event_id=appointment.google_event_id,
            changes=CalendarEventUpdate(starts_at=new_starts_at, ends_at=new_ends_at),
        )
        appointment.starts_at = new_starts_at
        appointment.ends_at = new_ends_at
        appointment.status = "rescheduled"
        self._db.commit()
        self._db.refresh(appointment)
        return appointment

    def cancel_appointment(self, *, appointment_id: uuid.UUID) -> Appointment:
        appointment = get_scoped(self._db, Appointment, self._business_id, appointment_id)
        if appointment is None:
            raise ValueError("Appointment not found for this business")

        self._provider.cancel_event(
            calendar_id=self._calendar_id, event_id=appointment.google_event_id
        )
        appointment.status = "cancelled"
        self._db.commit()
        self._db.refresh(appointment)
        return appointment
