"""Tests for AppointmentService (provider-agnostic, exercised against the mock provider)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.calendar.providers.base import (
    CalendarAlreadyCancelledError,
    CalendarConflictError,
    CalendarEventDraft,
    CalendarProviderUnavailableError,
    CalendarValidationError,
)
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService, get_upcoming_appointments
from app.models import Appointment, Business, Customer

# A fixed offset from the real current time, not a hardcoded date — a
# literal past date rots the moment "today" catches up to it (Sprint 83).
# +1 day keeps every `NOW + timedelta(hours=N)` below comfortably in the
# future for AppointmentService's own past-date validation.
NOW = (datetime.now(timezone.utc) + timedelta(days=1)).replace(minute=0, second=0, microsecond=0)


def _business_and_customer(db, name="Clinic A"):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    db.commit()
    return biz, customer


def _service(db, business_id, **provider_kwargs) -> AppointmentService:
    provider = MockCalendarProvider(**provider_kwargs)
    return AppointmentService(db, business_id, provider, calendar_id="primary")


def test_book_appointment_creates_row_and_sets_event_id(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)

    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )

    assert appointment.status == "booked"
    assert appointment.google_event_id == "mock-event-1"
    # starts_at/ends_at are naive TIMESTAMP columns (consistent with the rest of
    # the schema) — Postgres round-trips them without tzinfo.
    assert appointment.starts_at == starts_at.replace(tzinfo=None)
    assert appointment.ends_at == ends_at.replace(tzinfo=None)

    stored = db_session.scalars(select(Appointment).where(Appointment.id == appointment.id)).first()
    assert stored is not None


def test_book_appointment_conflict_leaves_no_row(db_session):
    biz, customer = _business_and_customer(db_session)
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)
    busy = MockCalendarProvider()
    busy.create_event(
        calendar_id="primary",
        draft=CalendarEventDraft(starts_at=starts_at, ends_at=ends_at, summary="Existing"),
    )
    service = AppointmentService(db_session, biz.id, busy, calendar_id="primary")

    with pytest.raises(CalendarConflictError):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=starts_at,
            ends_at=ends_at,
            summary="Double-booked",
        )

    assert db_session.scalars(select(Appointment)).all() == []


def test_book_appointment_commit_failure_cleans_up_external_event(db_session, monkeypatch):
    biz, customer = _business_and_customer(db_session)
    provider = MockCalendarProvider()
    service = AppointmentService(db_session, biz.id, provider, calendar_id="primary")
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)

    original_commit = db_session.commit
    commit_calls = {"n": 0}

    def failing_commit():
        commit_calls["n"] += 1
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    cancel_spy = Mock(wraps=provider.cancel_event)
    monkeypatch.setattr(provider, "cancel_event", cancel_spy)

    with pytest.raises(SQLAlchemyError, match="simulated commit failure"):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=starts_at,
            ends_at=ends_at,
            summary="Dental cleaning",
        )

    # Cleanup attempted exactly once, against the event that was actually created.
    cancel_spy.assert_called_once_with(calendar_id="primary", event_id="mock-event-1")
    assert provider._events["mock-event-1"].status == "cancelled"

    # No Appointment row survives a failed commit.
    monkeypatch.setattr(db_session, "commit", original_commit)
    assert db_session.scalars(select(Appointment)).all() == []


def test_book_appointment_cleanup_failure_does_not_hide_original_exception(db_session, monkeypatch):
    biz, customer = _business_and_customer(db_session)
    provider = MockCalendarProvider()
    service = AppointmentService(db_session, biz.id, provider, calendar_id="primary")
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)

    def failing_commit():
        raise SQLAlchemyError("simulated commit failure")

    def failing_cancel(*, calendar_id, event_id):
        raise CalendarProviderUnavailableError("cleanup also failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    cancel_spy = Mock(side_effect=failing_cancel)
    monkeypatch.setattr(provider, "cancel_event", cancel_spy)

    with pytest.raises(SQLAlchemyError, match="simulated commit failure"):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=starts_at,
            ends_at=ends_at,
            summary="Dental cleaning",
        )

    cancel_spy.assert_called_once_with(calendar_id="primary", event_id="mock-event-1")


def test_reschedule_appointment_updates_row_and_calls_provider(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )

    new_starts_at = NOW + timedelta(hours=5)
    new_ends_at = new_starts_at + timedelta(minutes=30)
    rescheduled = service.reschedule_appointment(
        appointment_id=appointment.id, new_starts_at=new_starts_at, new_ends_at=new_ends_at
    )

    assert rescheduled.status == "rescheduled"
    assert rescheduled.starts_at == new_starts_at.replace(tzinfo=None)
    assert rescheduled.ends_at == new_ends_at.replace(tzinfo=None)


def test_cancel_appointment_updates_status(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )

    cancelled = service.cancel_appointment(appointment_id=appointment.id)

    assert cancelled.status == "cancelled"


def test_reschedule_is_tenant_scoped(db_session):
    biz_a, customer_a = _business_and_customer(db_session, "Clinic A")
    biz_b, _ = _business_and_customer(db_session, "Clinic B")
    service_a = _service(db_session, biz_a.id)
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service_a.book_appointment(
        customer_id=customer_a.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )

    service_b = _service(db_session, biz_b.id)
    with pytest.raises(ValueError, match="not found"):
        service_b.reschedule_appointment(
            appointment_id=appointment.id,
            new_starts_at=starts_at + timedelta(hours=1),
            new_ends_at=ends_at + timedelta(hours=1),
        )


def test_list_availability_delegates_to_provider(db_session):
    biz, _ = _business_and_customer(db_session)
    starts_at = NOW + timedelta(hours=1)
    ends_at = starts_at + timedelta(minutes=30)
    service = _service(db_session, biz.id)

    slots = service.list_availability(starts_at=starts_at, ends_at=ends_at)

    assert len(slots) == 1
    assert slots[0].starts_at == starts_at
    assert slots[0].ends_at == ends_at


# --- get_upcoming_appointments (DEC-034 — shared by app/ai/tools.py and app/ai/context.py) --


def test_get_upcoming_appointments_returns_soonest_first(db_session):
    # get_upcoming_appointments filters on starts_at > datetime.now(), so
    # "sooner" must be anchored to the real current time rather than the
    # module's fixed NOW constant — otherwise it silently drifts into the
    # past as real time passes NOW and disappears from the query results
    # (the fixed NOW + 1 hour eventually becomes yesterday).
    now = datetime.now(timezone.utc)
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    later = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=now + timedelta(days=2),
        ends_at=now + timedelta(days=2, minutes=30),
        summary="Later",
    )
    sooner = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=now + timedelta(hours=1),
        ends_at=now + timedelta(hours=1, minutes=30),
        summary="Sooner",
    )

    upcoming = get_upcoming_appointments(db_session, biz.id, customer.id)

    assert [a.id for a in upcoming] == [sooner.id, later.id]


def test_get_upcoming_appointments_respects_limit(db_session):
    # Anchored to the real current time, not the module's fixed NOW constant
    # — see test_get_upcoming_appointments_returns_soonest_first above for why.
    now = datetime.now(timezone.utc)
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    for i in range(3):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=now + timedelta(days=i + 1),
            ends_at=now + timedelta(days=i + 1, minutes=30),
            summary=f"Appt {i}",
        )

    upcoming = get_upcoming_appointments(db_session, biz.id, customer.id, limit=2)

    assert len(upcoming) == 2


def test_get_upcoming_appointments_excludes_past_and_cancelled(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    cancelled = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=1, minutes=30),
        summary="Will cancel",
    )
    service.cancel_appointment(appointment_id=cancelled.id)
    past = Appointment(
        business_id=biz.id,
        customer_id=customer.id,
        starts_at=NOW - timedelta(days=1),
        ends_at=NOW - timedelta(days=1) + timedelta(minutes=30),
        status="booked",
    )
    db_session.add(past)
    db_session.commit()

    upcoming = get_upcoming_appointments(db_session, biz.id, customer.id)

    assert upcoming == []


def test_get_upcoming_appointments_empty_for_customer_with_none(db_session):
    biz, customer = _business_and_customer(db_session)

    assert get_upcoming_appointments(db_session, biz.id, customer.id) == []


# --- Sprint 83 (production bug fix, DEC-059): write-path validation --------
# AppointmentService.book_appointment()/reschedule_appointment() previously
# trusted the caller-supplied window as-is — no working-hours check (only
# list_availability() had one), no past-date check, no start<end check, and
# a cancelled appointment could be silently resurrected by rescheduling it.
# All four are live-reproduced bugs; see app/calendar/service.py's
# _validate_booking_window and app/calendar/providers/base.py's two new
# exception types for the fix itself.


def test_book_appointment_rejects_a_time_outside_working_hours(db_session):
    biz, customer = _business_and_customer(db_session)
    working_hours = {
        "mon": {"open": "09:00", "close": "17:00"},
        "tue": {"open": "09:00", "close": "17:00"},
        "wed": {"open": "09:00", "close": "17:00"},
        "thu": {"open": "09:00", "close": "17:00"},
        "fri": {"open": "09:00", "close": "17:00"},
        "sat": None,
        "sun": None,
    }
    provider = MockCalendarProvider()
    service = AppointmentService(
        db_session, biz.id, provider, calendar_id="primary", timezone="UTC",
        working_hours=working_hours,
    )
    # The next Sunday — a day this business is closed, regardless of when
    # the suite runs.
    now = datetime.now(timezone.utc)
    days_until_sunday = (6 - now.weekday()) % 7 or 7
    closed_day = (now + timedelta(days=days_until_sunday)).replace(
        hour=23, minute=0, second=0, microsecond=0
    )

    with pytest.raises(CalendarValidationError, match="outside business hours"):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=closed_day,
            ends_at=closed_day + timedelta(minutes=30),
            summary="Should be rejected",
        )
    assert db_session.scalars(select(Appointment)).all() == []


def test_book_appointment_with_no_working_hours_configured_is_unrestricted(db_session):
    """working_hours=None means "not configured yet" (app/models.py's own
    Business.working_hours docstring) — every time is allowed, matching
    list_availability's existing behavior for the same case."""
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)  # no working_hours kwarg -> None

    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=1, minutes=30),
        summary="Any time is fine",
    )
    assert appointment.status == "booked"


def test_book_appointment_rejects_a_past_start_time(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    past = datetime.now(timezone.utc) - timedelta(days=5)

    with pytest.raises(CalendarValidationError, match="in the past"):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=past,
            ends_at=past + timedelta(minutes=30),
            summary="Should be rejected",
        )
    assert db_session.scalars(select(Appointment)).all() == []


def test_book_appointment_rejects_end_before_start(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=1)

    with pytest.raises(CalendarValidationError, match="end time must be after"):
        service.book_appointment(
            customer_id=customer.id,
            conversation_id=None,
            starts_at=starts_at,
            ends_at=starts_at - timedelta(hours=1),
            summary="Should be rejected",
        )
    assert db_session.scalars(select(Appointment)).all() == []


def test_reschedule_rejects_an_already_cancelled_appointment(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=1, minutes=30),
        summary="Will cancel",
    )
    service.cancel_appointment(appointment_id=appointment.id)

    with pytest.raises(CalendarAlreadyCancelledError):
        service.reschedule_appointment(
            appointment_id=appointment.id,
            new_starts_at=NOW + timedelta(hours=5),
            new_ends_at=NOW + timedelta(hours=5, minutes=30),
        )

    # The appointment stays cancelled — not silently resurrected.
    db_session.refresh(appointment)
    assert appointment.status == "cancelled"


def test_reschedule_rejects_end_before_start(db_session):
    biz, customer = _business_and_customer(db_session)
    service = _service(db_session, biz.id)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=NOW + timedelta(hours=1),
        ends_at=NOW + timedelta(hours=1, minutes=30),
        summary="Original",
    )

    with pytest.raises(CalendarValidationError, match="end time must be after"):
        service.reschedule_appointment(
            appointment_id=appointment.id,
            new_starts_at=NOW + timedelta(hours=5),
            new_ends_at=NOW + timedelta(hours=4),
        )
