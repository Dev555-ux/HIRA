"""Tests for app/calendar/providers/internal.py: InternalSchedulerProvider
against a real (test) Postgres session — no network access, no Google
credentials, no mocking of the provider itself (Sprint 78)."""

import uuid
from datetime import datetime, timedelta

import pytest

from app.calendar.providers.base import (
    CalendarConflictError,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarNotFoundError,
    TimeSlot,
)
from app.calendar.providers.internal import InternalSchedulerProvider
from app.models import Appointment, Business, Customer

# Naive, matching how Appointment.starts_at/ends_at are actually stored (DEC-032)
# and how a real AI tool call's datetime.fromisoformat(...) window arrives —
# unlike test_google_calendar_provider.py, this provider reads real DB rows,
# so a tz-aware NOW here would raise on the naive/aware comparison in
# invert_busy_periods the moment a busy period from the database is involved.
NOW = datetime(2026, 8, 3, 9, 0)


def _slot(hours_from_now: float, duration_minutes: int = 60) -> TimeSlot:
    start = NOW + timedelta(hours=hours_from_now)
    return TimeSlot(starts_at=start, ends_at=start + timedelta(minutes=duration_minutes))


@pytest.fixture
def business(db_session) -> Business:
    biz = Business(name="Clinic A")
    db_session.add(biz)
    db_session.flush()
    return biz


@pytest.fixture
def customer(db_session, business) -> Customer:
    cust = Customer(business_id=business.id, wa_phone="+15550001111")
    db_session.add(cust)
    db_session.flush()
    return cust


def _book(db_session, business, customer, slot: TimeSlot, *, status: str = "booked") -> Appointment:
    appt = Appointment(
        business_id=business.id,
        customer_id=customer.id,
        google_event_id=f"internal-{uuid.uuid4()}",
        starts_at=slot.starts_at,
        ends_at=slot.ends_at,
        status=status,
    )
    db_session.add(appt)
    db_session.flush()
    return appt


# --- get_availability ---------------------------------------------------


def test_get_availability_returns_whole_window_when_nothing_booked(db_session, business):
    provider = InternalSchedulerProvider(db_session, business.id)
    window = _slot(0, 480)

    assert provider.get_availability(calendar_id="internal", window=window) == [window]


def test_get_availability_excludes_a_booked_appointment(db_session, business, customer):
    provider = InternalSchedulerProvider(db_session, business.id)
    window = _slot(0, 480)  # 09:00-17:00
    _book(db_session, business, customer, TimeSlot(NOW.replace(hour=11), NOW.replace(hour=12)))

    free = provider.get_availability(calendar_id="internal", window=window)

    assert free == [
        TimeSlot(starts_at=window.starts_at, ends_at=NOW.replace(hour=11)),
        TimeSlot(starts_at=NOW.replace(hour=12), ends_at=window.ends_at),
    ]


def test_get_availability_ignores_a_cancelled_appointment(db_session, business, customer):
    provider = InternalSchedulerProvider(db_session, business.id)
    window = _slot(0, 480)
    _book(
        db_session,
        business,
        customer,
        TimeSlot(NOW.replace(hour=11), NOW.replace(hour=12)),
        status="cancelled",
    )

    assert provider.get_availability(calendar_id="internal", window=window) == [window]


def test_get_availability_only_looks_at_this_business(db_session, business, customer):
    other_biz = Business(name="Clinic B")
    db_session.add(other_biz)
    db_session.flush()
    other_customer = Customer(business_id=other_biz.id, wa_phone="+15559998888")
    db_session.add(other_customer)
    db_session.flush()
    _book(
        db_session,
        other_biz,
        other_customer,
        TimeSlot(NOW.replace(hour=11), NOW.replace(hour=12)),
    )

    provider = InternalSchedulerProvider(db_session, business.id)
    window = _slot(0, 480)

    assert provider.get_availability(calendar_id="internal", window=window) == [window]


# --- create_event ---------------------------------------------------------


def test_create_event_succeeds_for_a_free_slot(db_session, business):
    provider = InternalSchedulerProvider(db_session, business.id)
    slot = _slot(2)

    event = provider.create_event(
        calendar_id="internal",
        draft=CalendarEventDraft(
            starts_at=slot.starts_at, ends_at=slot.ends_at, summary="Cleaning"
        ),
    )

    assert event.status == "confirmed"
    assert event.starts_at == slot.starts_at
    assert event.provider_event_id.startswith("internal-")


def test_create_event_raises_conflict_for_an_overlapping_slot(db_session, business, customer):
    provider = InternalSchedulerProvider(db_session, business.id)
    existing = _slot(2)
    _book(db_session, business, customer, existing)

    with pytest.raises(CalendarConflictError):
        provider.create_event(
            calendar_id="internal",
            draft=CalendarEventDraft(
                starts_at=existing.starts_at + timedelta(minutes=30),
                ends_at=existing.ends_at + timedelta(minutes=30),
                summary="Overlapping",
            ),
        )


# --- update_event (reschedule) --------------------------------------------


def test_update_event_moves_to_a_free_slot(db_session, business, customer):
    provider = InternalSchedulerProvider(db_session, business.id)
    original = _slot(2)
    appt = _book(db_session, business, customer, original)
    new_slot = _slot(5)

    event = provider.update_event(
        calendar_id="internal",
        event_id=appt.google_event_id,
        changes=CalendarEventUpdate(starts_at=new_slot.starts_at, ends_at=new_slot.ends_at),
    )

    assert event.starts_at == new_slot.starts_at
    assert event.ends_at == new_slot.ends_at


def test_update_event_does_not_conflict_with_its_own_current_slot(db_session, business, customer):
    """Rescheduling to a slightly-overlapping-but-mostly-same time must not
    treat the appointment's own existing row as a conflict with itself."""
    provider = InternalSchedulerProvider(db_session, business.id)
    original = _slot(2)
    appt = _book(db_session, business, customer, original)

    event = provider.update_event(
        calendar_id="internal",
        event_id=appt.google_event_id,
        changes=CalendarEventUpdate(ends_at=original.ends_at + timedelta(minutes=15)),
    )

    assert event.ends_at == original.ends_at + timedelta(minutes=15)


def test_update_event_raises_conflict_when_new_slot_overlaps_another_appointment(
    db_session, business, customer
):
    provider = InternalSchedulerProvider(db_session, business.id)
    first = _slot(2)
    second = _slot(5)
    appt = _book(db_session, business, customer, first)
    _book(db_session, business, customer, second)

    with pytest.raises(CalendarConflictError):
        provider.update_event(
            calendar_id="internal",
            event_id=appt.google_event_id,
            changes=CalendarEventUpdate(starts_at=second.starts_at, ends_at=second.ends_at),
        )


def test_update_event_raises_not_found_for_an_unknown_event_id(db_session, business):
    provider = InternalSchedulerProvider(db_session, business.id)

    with pytest.raises(CalendarNotFoundError):
        provider.update_event(
            calendar_id="internal",
            event_id="internal-does-not-exist",
            changes=CalendarEventUpdate(starts_at=NOW, ends_at=NOW + timedelta(hours=1)),
        )


# --- cancel_event -----------------------------------------------------------


def test_cancel_event_succeeds_for_an_existing_appointment(db_session, business, customer):
    provider = InternalSchedulerProvider(db_session, business.id)
    appt = _book(db_session, business, customer, _slot(2))

    provider.cancel_event(calendar_id="internal", event_id=appt.google_event_id)  # no raise


def test_cancel_event_raises_not_found_for_an_unknown_event_id(db_session, business):
    provider = InternalSchedulerProvider(db_session, business.id)

    with pytest.raises(CalendarNotFoundError):
        provider.cancel_event(calendar_id="internal", event_id="internal-does-not-exist")


def test_a_cancelled_appointments_slot_becomes_bookable_again(db_session, business, customer):
    provider = InternalSchedulerProvider(db_session, business.id)
    slot = _slot(2)
    appt = _book(db_session, business, customer, slot)

    provider.cancel_event(calendar_id="internal", event_id=appt.google_event_id)
    appt.status = "cancelled"  # cancel_event is validate-only; the service applies this
    db_session.flush()

    event = provider.create_event(
        calendar_id="internal",
        draft=CalendarEventDraft(starts_at=slot.starts_at, ends_at=slot.ends_at, summary="Refill"),
    )
    assert event.status == "confirmed"
