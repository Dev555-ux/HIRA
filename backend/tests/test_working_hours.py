"""Tests for app/calendar/working_hours.py: intersecting raw calendar
free/busy slots with a business's configured working hours + timezone
(DEC-032)."""

from datetime import datetime, timezone

from app.calendar.providers.base import TimeSlot
from app.calendar.working_hours import filter_by_working_hours

HOURS = {
    "mon": {"open": "09:00", "close": "17:00"},
    "tue": {"open": "09:00", "close": "17:00"},
    "wed": {"open": "09:00", "close": "17:00"},
    "thu": {"open": "09:00", "close": "17:00"},
    "fri": {"open": "09:00", "close": "17:00"},
    "sat": None,
    "sun": None,
}


def _slot(start_iso: str, end_iso: str) -> TimeSlot:
    return TimeSlot(
        starts_at=datetime.fromisoformat(start_iso).replace(tzinfo=timezone.utc),
        ends_at=datetime.fromisoformat(end_iso).replace(tzinfo=timezone.utc),
    )


def test_returns_slots_unchanged_when_working_hours_not_configured():
    slots = [_slot("2026-08-03T10:00", "2026-08-03T11:00")]  # a Monday

    result = filter_by_working_hours(slots, working_hours=None, timezone="UTC")

    assert result == slots


def test_clips_a_slot_fully_within_working_hours():
    slots = [_slot("2026-08-03T10:00", "2026-08-03T11:00")]  # Monday, within 9-17

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="UTC")

    assert result == slots


def test_clips_a_slot_that_starts_before_opening():
    slots = [_slot("2026-08-03T07:00", "2026-08-03T10:00")]  # Monday, opens at 9

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="UTC")

    assert len(result) == 1
    assert result[0].starts_at == datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)
    assert result[0].ends_at == datetime(2026, 8, 3, 10, 0, tzinfo=timezone.utc)


def test_clips_a_slot_that_ends_after_closing():
    slots = [_slot("2026-08-03T16:00", "2026-08-03T19:00")]  # Monday, closes at 17

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="UTC")

    assert len(result) == 1
    assert result[0].starts_at == datetime(2026, 8, 3, 16, 0, tzinfo=timezone.utc)
    assert result[0].ends_at == datetime(2026, 8, 3, 17, 0, tzinfo=timezone.utc)


def test_drops_a_slot_entirely_on_a_closed_day():
    slots = [_slot("2026-08-01T10:00", "2026-08-01T11:00")]  # a Saturday

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="UTC")

    assert result == []


def test_splits_a_multi_day_slot_into_one_window_per_open_day():
    # Friday 16:00 through Tuesday 10:00 — spans Fri (open), Sat/Sun (closed), Mon (open), Tue (open, but slot ends at 10:00)
    slots = [_slot("2026-07-31T16:00", "2026-08-04T10:00")]

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="UTC")

    assert len(result) == 3
    assert result[0] == _slot("2026-07-31T16:00", "2026-07-31T17:00")  # Fri
    assert result[1] == _slot("2026-08-03T09:00", "2026-08-03T17:00")  # Mon
    assert result[2] == _slot("2026-08-04T09:00", "2026-08-04T10:00")  # Tue


def test_respects_business_timezone_not_utc():
    # 09:00 Mon in America/New_York (UTC-4 in August, DST) is 13:00 UTC.
    slots = [_slot("2026-08-03T12:00", "2026-08-03T14:00")]  # 08:00-10:00 local

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="America/New_York")

    # Local open is 09:00 -> 13:00 UTC; slot starts at 12:00 UTC (08:00 local), so clipped to 13:00 UTC start.
    assert len(result) == 1
    assert result[0].starts_at == datetime(2026, 8, 3, 13, 0, tzinfo=timezone.utc)
    assert result[0].ends_at == datetime(2026, 8, 3, 14, 0, tzinfo=timezone.utc)


def test_falls_back_to_utc_for_unknown_timezone():
    # Regression: a business with an invalid/legacy timezone value (e.g.
    # "asia" instead of "Asia/Kolkata") must not crash availability lookups —
    # falls back to treating the business as UTC instead.
    slots = [_slot("2026-08-03T10:00", "2026-08-03T11:00")]  # a Monday

    result = filter_by_working_hours(slots, working_hours=HOURS, timezone="asia")

    assert result == slots
