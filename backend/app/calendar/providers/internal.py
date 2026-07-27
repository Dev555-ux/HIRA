"""Internal scheduling provider — powers "HIRA Calendar" (Sprint 78/79).

Used automatically by app/calendar/factory.py whenever a business hasn't
connected an external Google Calendar. Product-facing, this *is* the
business's calendar (Sprint 79: promoted from stopgap fallback to the
default, first-class scheduling experience) — "Internal Scheduler"/
"InternalSchedulerProvider" is this module's own implementation name and
must never appear in customer- or founder-facing copy. Implements the exact
same CalendarProvider interface GoogleCalendarProvider does, so
AppointmentService, the AI's booking tools, Execution Traces, and
Conversation Replay all keep working unmodified regardless of which provider
is active underneath — none of them import or know about this class.

Availability and conflict-checking are computed directly from this
business's own `Appointment` rows — the exact same table a Google-backed
booking already writes to — rather than a separate calendar; there is no
external system involved for this provider at all.

Division of responsibility mirrors Google's provider exactly: the
Appointment row itself is written by AppointmentService, not here. This
class only validates conflicts/existence and returns a CalendarEvent.
create_event's `provider_event_id` is a freshly generated synthetic id
(there's no external system to assign one) that the caller stores into
Appointment.google_event_id exactly as it would a real Google event id — so
that column, and everything downstream that keys off it (reschedule/cancel
lookups, the tool-call compensation path in app/ai/tools.py), needs no
changes at all.

If this business later connects a real Google Calendar, app/calendar/
factory.py::get_appointment_service starts returning a GoogleCalendarProvider
again automatically — nothing here needs to change or be torn down.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendar.providers.base import (
    CalendarConflictError,
    CalendarEvent,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarNotFoundError,
    CalendarProvider,
    TimeSlot,
    invert_busy_periods,
)
from app.models import Appointment

_ACTIVE_STATUSES = ("booked", "rescheduled")


class InternalSchedulerProvider(CalendarProvider):
    """`calendar_id` is accepted (interface conformance) but unused — there is
    exactly one internal schedule per business, not one per named calendar."""

    def __init__(self, db: Session, business_id: uuid.UUID):
        self._db = db
        self._business_id = business_id

    def _overlapping_appointments(
        self, window: TimeSlot, *, exclude_event_id: str | None = None
    ) -> list[Appointment]:
        query = select(Appointment).where(
            Appointment.business_id == self._business_id,
            Appointment.status.in_(_ACTIVE_STATUSES),
            Appointment.starts_at < window.ends_at,
            Appointment.ends_at > window.starts_at,
        )
        if exclude_event_id is not None:
            query = query.where(Appointment.google_event_id != exclude_event_id)
        return list(self._db.scalars(query).all())

    def _get_by_event_id(self, event_id: str) -> Appointment:
        appointment = self._db.scalars(
            select(Appointment).where(
                Appointment.business_id == self._business_id,
                Appointment.google_event_id == event_id,
            )
        ).first()
        if appointment is None:
            raise CalendarNotFoundError(f"No internally-scheduled appointment {event_id!r}")
        return appointment

    def get_availability(self, *, calendar_id: str, window: TimeSlot) -> list[TimeSlot]:
        busy = [
            TimeSlot(starts_at=a.starts_at, ends_at=a.ends_at)
            for a in self._overlapping_appointments(window)
        ]
        return invert_busy_periods(window, busy)

    def create_event(self, *, calendar_id: str, draft: CalendarEventDraft) -> CalendarEvent:
        window = TimeSlot(starts_at=draft.starts_at, ends_at=draft.ends_at)
        if self._overlapping_appointments(window):
            raise CalendarConflictError("Requested slot overlaps an existing appointment")
        return CalendarEvent(
            provider_event_id=f"internal-{uuid.uuid4()}",
            starts_at=draft.starts_at,
            ends_at=draft.ends_at,
            status="confirmed",
        )

    def update_event(
        self, *, calendar_id: str, event_id: str, changes: CalendarEventUpdate
    ) -> CalendarEvent:
        appointment = self._get_by_event_id(event_id)
        starts_at: datetime = changes.starts_at or appointment.starts_at
        ends_at: datetime = changes.ends_at or appointment.ends_at
        window = TimeSlot(starts_at=starts_at, ends_at=ends_at)
        if self._overlapping_appointments(window, exclude_event_id=event_id):
            raise CalendarConflictError("Requested slot overlaps an existing appointment")
        return CalendarEvent(
            provider_event_id=event_id, starts_at=starts_at, ends_at=ends_at, status="confirmed"
        )

    def cancel_event(self, *, calendar_id: str, event_id: str) -> None:
        self._get_by_event_id(event_id)  # raises CalendarNotFoundError if missing
