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

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendar.providers.base import (
    CalendarAlreadyCancelledError,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarProvider,
    CalendarValidationError,
    TimeSlot,
)
from app.calendar.working_hours import filter_by_working_hours
from app.db.tenant import get_scoped
from app.models import Appointment

logger = logging.getLogger(__name__)


def get_upcoming_appointments(
    db: Session,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    limit: int | None = None,
) -> list[Appointment]:
    """This customer's not-yet-started, non-cancelled appointments, soonest
    first. A plain local read of already-booked `Appointment` rows — no
    `CalendarProvider`/stored credentials needed, unlike `list_availability`.

    Shared by app/ai/tools.py (reschedule/cancel dispatch, limit=1) and
    app/ai/context.py (prompt grounding, limit=3) — DEC-034.
    """
    query = (
        select(Appointment)
        .where(
            Appointment.business_id == business_id,
            Appointment.customer_id == customer_id,
            Appointment.status.in_(["booked", "rescheduled"]),
            Appointment.starts_at > datetime.now(timezone.utc),
        )
        .order_by(Appointment.starts_at)
    )
    if limit is not None:
        query = query.limit(limit)
    return list(db.scalars(query).all())


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

    def _validate_booking_window(self, starts_at: datetime, ends_at: datetime) -> None:
        """Shared write-path guard for book_appointment/reschedule_appointment.

        The caller-supplied datetimes (an AI tool call's arguments, or the
        REST API's request body) were previously trusted as-is and passed
        straight to the provider — nothing rejected a past date, an inverted
        range, or a time outside working hours before it reached the
        calendar/database. This mirrors list_availability's existing
        working-hours check (filter_by_working_hours, below) rather than
        introducing a second way to apply the same rule, and runs before any
        provider call so an invalid request never reaches the provider or
        writes anything.

        Naive datetimes are treated as UTC (DEC-032, matching every other
        datetime this schema stores) rather than assumed local, so this
        behaves the same regardless of whether a caller's ISO string
        included an explicit UTC offset.
        """
        starts = (
            starts_at if starts_at.tzinfo is not None else starts_at.replace(tzinfo=timezone.utc)
        )
        ends = ends_at if ends_at.tzinfo is not None else ends_at.replace(tzinfo=timezone.utc)

        if ends <= starts:
            raise CalendarValidationError("The end time must be after the start time.")
        if starts < datetime.now(timezone.utc):
            raise CalendarValidationError("Cannot book an appointment in the past.")
        if self._working_hours:
            window = TimeSlot(starts_at=starts, ends_at=ends)
            allowed = filter_by_working_hours(
                [window], working_hours=self._working_hours, timezone=self._timezone
            )
            if allowed != [window]:
                raise CalendarValidationError("This time is outside business hours.")

    def book_appointment(
        self,
        *,
        customer_id: uuid.UUID,
        conversation_id: uuid.UUID | None,
        starts_at: datetime,
        ends_at: datetime,
        summary: str,
        commit: bool = True,
    ) -> Appointment:
        """Create the event on the calendar, then persist the Appointment row.

        Raises CalendarValidationError if the requested window itself is
        invalid (past, inverted, or outside working hours) — checked before
        the provider is ever called, so nothing is written in that case
        either. Also raises whatever the provider itself raises (e.g.
        CalendarConflictError) if the event can't be created — no
        Appointment row is written in that case.

        `commit=True` (default): commits immediately, matching every existing
        caller (the REST /appointments endpoint, the demo seed script, direct
        callers in tests) exactly as before. If that commit fails, the event
        would otherwise be left dangling on the external calendar with
        nothing in Postgres pointing to it — it's deleted best-effort via
        `cancel_calendar_event`, and the original commit error is re-raised
        either way (Section A2).

        `commit=False`: only flushes (assigns the row's id, surfaces
        constraint errors), leaving the commit to the caller. Used by
        execute_tool_call(commit=False) so the Assisted/Autonomous approval
        workflows (app/services/replies.py, app/ai/processing.py) can persist
        this Appointment and the Message row it's linked to in one atomic
        commit (Section A4) — such a caller is responsible for calling
        `cancel_calendar_event(...)` itself if its own, later commit fails.
        """
        self._validate_booking_window(starts_at, ends_at)
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
        if not commit:
            self._db.flush()
            return appointment

        try:
            self._db.commit()
        except Exception:
            self.cancel_calendar_event(event.provider_event_id)
            raise
        self._db.refresh(appointment)
        return appointment

    def cancel_calendar_event(self, event_id: str) -> None:
        """Best-effort delete of an external event. Logs but never raises —
        a cleanup failure must never mask the real error that triggered it.

        Used internally by book_appointment(commit=True), and externally by
        a caller that booked with commit=False and whose own later commit
        failed (Section A4) — same compensating action either way.
        """
        try:
            self._provider.cancel_event(calendar_id=self._calendar_id, event_id=event_id)
        except Exception:
            logger.exception(
                "Failed to clean up external calendar event %s after local commit failure",
                event_id,
            )

    def reschedule_appointment(
        self,
        *,
        appointment_id: uuid.UUID,
        new_starts_at: datetime,
        new_ends_at: datetime,
    ) -> Appointment:
        """Raises CalendarAlreadyCancelledError if the appointment was
        already cancelled — it must be re-booked, not silently resurrected
        by moving it to a new time — and CalendarValidationError for the
        same invalid-window cases book_appointment rejects (past, inverted,
        outside working hours), checked before the provider is called."""
        appointment = get_scoped(self._db, Appointment, self._business_id, appointment_id)
        if appointment is None:
            raise ValueError("Appointment not found for this business")
        if appointment.status == "cancelled":
            raise CalendarAlreadyCancelledError(
                "This appointment has already been cancelled and can't be rescheduled"
            )
        self._validate_booking_window(new_starts_at, new_ends_at)

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
