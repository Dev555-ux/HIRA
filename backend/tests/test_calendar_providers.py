"""Tests for the calendar provider interface (factory + MockCalendarProvider)."""

from datetime import datetime, timedelta, timezone

import pytest

from app.calendar.providers import CalendarError, get_calendar_provider
from app.calendar.providers.base import (
    CalendarConflictError,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarNotFoundError,
    TimeSlot,
)
from app.calendar.providers.mock import MockCalendarProvider

NOW = datetime(2026, 7, 10, 9, 0, tzinfo=timezone.utc)


def _slot(hours_from_now: float, duration_minutes: int = 30) -> TimeSlot:
    start = NOW + timedelta(hours=hours_from_now)
    return TimeSlot(starts_at=start, ends_at=start + timedelta(minutes=duration_minutes))


# --- factory ---------------------------------------------------------------


def test_get_calendar_provider_returns_mock():
    provider = get_calendar_provider("mock")
    assert isinstance(provider, MockCalendarProvider)


def test_get_calendar_provider_unknown_name_raises():
    with pytest.raises(CalendarError, match="Unknown calendar provider"):
        get_calendar_provider("google")


def test_get_calendar_provider_not_cached():
    a = get_calendar_provider("mock")
    b = get_calendar_provider("mock")
    assert a is not b  # deliberately uncached — see providers/__init__.py docstring


# --- MockCalendarProvider ----------------------------------------------------


def test_create_event_then_available_slot_is_free():
    provider = MockCalendarProvider()
    window = _slot(1)
    assert provider.get_availability(calendar_id="cal1", window=window) == [window]


def test_create_event_blocks_availability_and_future_bookings():
    provider = MockCalendarProvider()
    window = _slot(1)
    provider.create_event(
        calendar_id="cal1",
        draft=CalendarEventDraft(starts_at=window.starts_at, ends_at=window.ends_at, summary="Cleaning"),
    )

    assert provider.get_availability(calendar_id="cal1", window=window) == []
    with pytest.raises(CalendarConflictError):
        provider.create_event(
            calendar_id="cal1",
            draft=CalendarEventDraft(
                starts_at=window.starts_at, ends_at=window.ends_at, summary="Double-booked"
            ),
        )


def test_busy_windows_seed_unavailability():
    busy = _slot(2)
    provider = MockCalendarProvider(busy_windows=[busy])
    assert provider.get_availability(calendar_id="cal1", window=busy) == []


def test_update_event_reschedules():
    provider = MockCalendarProvider()
    window = _slot(1)
    event = provider.create_event(
        calendar_id="cal1",
        draft=CalendarEventDraft(starts_at=window.starts_at, ends_at=window.ends_at, summary="Cleaning"),
    )

    new_window = _slot(4)
    updated = provider.update_event(
        calendar_id="cal1",
        event_id=event.provider_event_id,
        changes=CalendarEventUpdate(starts_at=new_window.starts_at, ends_at=new_window.ends_at),
    )
    assert updated.starts_at == new_window.starts_at
    assert updated.ends_at == new_window.ends_at


def test_update_unknown_event_raises_not_found():
    provider = MockCalendarProvider()
    with pytest.raises(CalendarNotFoundError):
        provider.update_event(
            calendar_id="cal1", event_id="missing", changes=CalendarEventUpdate()
        )


def test_cancel_event_frees_the_slot():
    provider = MockCalendarProvider()
    window = _slot(1)
    event = provider.create_event(
        calendar_id="cal1",
        draft=CalendarEventDraft(starts_at=window.starts_at, ends_at=window.ends_at, summary="Cleaning"),
    )
    provider.cancel_event(calendar_id="cal1", event_id=event.provider_event_id)

    assert provider.get_availability(calendar_id="cal1", window=window) == [window]


def test_cancel_unknown_event_raises_not_found():
    provider = MockCalendarProvider()
    with pytest.raises(CalendarNotFoundError):
        provider.cancel_event(calendar_id="cal1", event_id="missing")


def test_fail_with_makes_every_method_raise():
    provider = MockCalendarProvider(fail_with=CalendarConflictError)
    window = _slot(1)
    with pytest.raises(CalendarConflictError):
        provider.get_availability(calendar_id="cal1", window=window)
    with pytest.raises(CalendarConflictError):
        provider.create_event(
            calendar_id="cal1",
            draft=CalendarEventDraft(starts_at=window.starts_at, ends_at=window.ends_at, summary="x"),
        )
