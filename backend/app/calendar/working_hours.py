"""Intersects raw calendar free/busy slots with a business's configured
working hours + timezone (DEC-032). Pure and provider-agnostic — reused by
both the dashboard's availability view and the AI's `check_availability` tool,
so working-hours logic exists in exactly one place.

`working_hours` shape: {"mon": {"open": "09:00", "close": "17:00"}, ...,
"sun": null} — a day's value is null/absent for "closed". The column itself
being None means "not configured yet"; callers should treat that as "no
restriction" (see Business.working_hours's docstring in app/models.py).
"""

from __future__ import annotations

from datetime import date, datetime, time as dt_time
from zoneinfo import ZoneInfo

from app.calendar.providers.base import TimeSlot

_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_time(value: str) -> dt_time:
    hour, minute = value.split(":")
    return dt_time(int(hour), int(minute))


def _next_day(d: date) -> date:
    return date.fromordinal(d.toordinal() + 1)


def filter_by_working_hours(
    slots: list[TimeSlot], *, working_hours: dict | None, timezone: str
) -> list[TimeSlot]:
    """Clip each slot to the portion(s) within working hours on their local
    day(s). Returns `slots` unchanged if `working_hours` is None."""
    if not working_hours:
        return slots

    tz = ZoneInfo(timezone)
    clipped: list[TimeSlot] = []
    for slot in slots:
        clipped.extend(_clip_slot(slot, working_hours, tz))
    return clipped


def _clip_slot(slot: TimeSlot, working_hours: dict, tz: ZoneInfo) -> list[TimeSlot]:
    result: list[TimeSlot] = []
    local_start = slot.starts_at.astimezone(tz)
    local_end = slot.ends_at.astimezone(tz)

    day = local_start.date()
    while day <= local_end.date():
        hours = working_hours.get(_DAY_KEYS[day.weekday()])
        if hours:
            day_open = datetime.combine(day, _parse_time(hours["open"]), tzinfo=tz)
            day_close = datetime.combine(day, _parse_time(hours["close"]), tzinfo=tz)
            window_start = max(local_start, day_open)
            window_end = min(local_end, day_close)
            if window_start < window_end:
                result.append(
                    TimeSlot(
                        starts_at=window_start.astimezone(slot.starts_at.tzinfo),
                        ends_at=window_end.astimezone(slot.ends_at.tzinfo),
                    )
                )
        day = _next_day(day)

    return result
