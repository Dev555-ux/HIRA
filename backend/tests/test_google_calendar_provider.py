"""Tests for app/calendar/providers/google.py: busy-period inversion (pure
function) and GoogleCalendarProvider against an injected fake API `service`
— no network access or real credentials (DEC-032)."""

from datetime import datetime, timedelta, timezone

import httplib2
import pytest
from googleapiclient.errors import HttpError

from app.calendar.providers.base import (
    CalendarAuthError,
    CalendarConflictError,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarNotFoundError,
    CalendarProviderUnavailableError,
    TimeSlot,
)
from app.calendar.providers.google import GoogleCalendarProvider, invert_busy_periods

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def _slot(hours_from_now: float, duration_minutes: int = 60) -> TimeSlot:
    start = NOW + timedelta(hours=hours_from_now)
    return TimeSlot(starts_at=start, ends_at=start + timedelta(minutes=duration_minutes))


def _http_error(status: int) -> HttpError:
    return HttpError(
        httplib2.Response({"status": status}), b"error body", uri="https://example.com"
    )


# --- invert_busy_periods (pure) ----------------------------------------------


def test_invert_busy_periods_no_busy_returns_whole_window():
    window = _slot(0, 480)
    assert invert_busy_periods(window, []) == [window]


def test_invert_busy_periods_splits_around_a_single_busy_block():
    window = _slot(0, 480)  # 09:00-17:00
    busy = [TimeSlot(starts_at=NOW.replace(hour=11), ends_at=NOW.replace(hour=12))]

    free = invert_busy_periods(window, busy)

    assert free == [
        TimeSlot(starts_at=window.starts_at, ends_at=NOW.replace(hour=11)),
        TimeSlot(starts_at=NOW.replace(hour=12), ends_at=window.ends_at),
    ]


def test_invert_busy_periods_busy_covers_entire_window():
    window = _slot(0, 60)
    busy = [TimeSlot(starts_at=window.starts_at, ends_at=window.ends_at)]

    assert invert_busy_periods(window, busy) == []


def test_invert_busy_periods_handles_unsorted_overlapping_busy_blocks():
    window = _slot(0, 480)  # 09:00-17:00
    busy = [
        TimeSlot(starts_at=NOW.replace(hour=14), ends_at=NOW.replace(hour=15)),
        TimeSlot(starts_at=NOW.replace(hour=10), ends_at=NOW.replace(hour=13)),  # out of order
    ]

    free = invert_busy_periods(window, busy)

    assert free == [
        TimeSlot(starts_at=window.starts_at, ends_at=NOW.replace(hour=10)),
        TimeSlot(starts_at=NOW.replace(hour=13), ends_at=NOW.replace(hour=14)),
        TimeSlot(starts_at=NOW.replace(hour=15), ends_at=window.ends_at),
    ]


# --- GoogleCalendarProvider ---------------------------------------------------


class _FakeExecutable:
    def __init__(self, result=None, error: HttpError | None = None):
        self._result = result
        self._error = error

    def execute(self):
        if self._error is not None:
            raise self._error
        return self._result


class _FakeFreeBusy:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error

    def query(self, body):
        self.last_body = body
        return _FakeExecutable(self._response, self._error)


class _FakeEvents:
    def __init__(self, insert_result=None, patch_result=None, error=None):
        self._insert_result = insert_result
        self._patch_result = patch_result
        self._error = error

    def insert(self, calendarId, body):
        self.last_insert = (calendarId, body)
        return _FakeExecutable(self._insert_result, self._error)

    def patch(self, calendarId, eventId, body):
        self.last_patch = (calendarId, eventId, body)
        return _FakeExecutable(self._patch_result, self._error)

    def delete(self, calendarId, eventId):
        self.last_delete = (calendarId, eventId)
        return _FakeExecutable(None, self._error)


class _FakeService:
    def __init__(self, freebusy=None, events=None):
        self._freebusy = freebusy or _FakeFreeBusy(
            response={"calendars": {"primary": {"busy": []}}}
        )
        self._events = events or _FakeEvents()

    def freebusy(self):
        return self._freebusy

    def events(self):
        return self._events


def test_get_availability_returns_free_slots(monkeypatch):
    freebusy = _FakeFreeBusy(
        response={
            "calendars": {
                "primary": {
                    "busy": [
                        {"start": "2026-08-03T11:00:00+00:00", "end": "2026-08-03T12:00:00+00:00"}
                    ]
                }
            }
        }
    )
    provider = GoogleCalendarProvider(service=_FakeService(freebusy=freebusy))

    slots = provider.get_availability(calendar_id="primary", window=_slot(0, 480))

    assert len(slots) == 2
    assert freebusy.last_body["items"] == [{"id": "primary"}]


def test_create_event_succeeds_when_slot_is_free():
    events = _FakeEvents(
        insert_result={
            "id": "evt-1",
            "status": "confirmed",
            "start": {"dateTime": "2026-08-03T10:00:00+00:00"},
            "end": {"dateTime": "2026-08-03T11:00:00+00:00"},
        }
    )
    provider = GoogleCalendarProvider(service=_FakeService(events=events))

    event = provider.create_event(
        calendar_id="primary",
        draft=CalendarEventDraft(
            starts_at=NOW.replace(hour=10), ends_at=NOW.replace(hour=11), summary="Cleaning"
        ),
    )

    assert event.provider_event_id == "evt-1"
    assert event.status == "confirmed"
    assert events.last_insert[1]["summary"] == "Cleaning"


def test_create_event_raises_conflict_when_slot_is_busy():
    freebusy = _FakeFreeBusy(
        response={
            "calendars": {
                "primary": {
                    "busy": [
                        {"start": "2026-08-03T10:00:00+00:00", "end": "2026-08-03T11:00:00+00:00"}
                    ]
                }
            }
        }
    )
    provider = GoogleCalendarProvider(service=_FakeService(freebusy=freebusy))

    with pytest.raises(CalendarConflictError):
        provider.create_event(
            calendar_id="primary",
            draft=CalendarEventDraft(
                starts_at=NOW.replace(hour=10), ends_at=NOW.replace(hour=11), summary="Cleaning"
            ),
        )


def test_create_event_embeds_attendee_name_in_description():
    events = _FakeEvents(
        insert_result={
            "id": "evt-1",
            "status": "confirmed",
            "start": {"dateTime": "2026-08-03T10:00:00+00:00"},
            "end": {"dateTime": "2026-08-03T11:00:00+00:00"},
        }
    )
    provider = GoogleCalendarProvider(service=_FakeService(events=events))

    provider.create_event(
        calendar_id="primary",
        draft=CalendarEventDraft(
            starts_at=NOW.replace(hour=10),
            ends_at=NOW.replace(hour=11),
            summary="Cleaning",
            attendee_name="Alex Rivera",
        ),
    )

    assert "Alex Rivera" in events.last_insert[1]["description"]


def test_update_event_returns_the_updated_event():
    events = _FakeEvents(
        patch_result={
            "id": "evt-1",
            "status": "confirmed",
            "start": {"dateTime": "2026-08-03T14:00:00+00:00"},
            "end": {"dateTime": "2026-08-03T15:00:00+00:00"},
        }
    )
    provider = GoogleCalendarProvider(service=_FakeService(events=events))

    updated = provider.update_event(
        calendar_id="primary",
        event_id="evt-1",
        changes=CalendarEventUpdate(starts_at=NOW.replace(hour=14), ends_at=NOW.replace(hour=15)),
    )

    assert updated.starts_at == datetime.fromisoformat("2026-08-03T14:00:00+00:00")
    assert events.last_patch[1] == "evt-1"


def test_cancel_event_calls_delete():
    events = _FakeEvents()
    provider = GoogleCalendarProvider(service=_FakeService(events=events))

    provider.cancel_event(calendar_id="primary", event_id="evt-1")

    assert events.last_delete == ("primary", "evt-1")


@pytest.mark.parametrize(
    "status,expected_error",
    [
        (401, CalendarAuthError),
        (403, CalendarAuthError),
        (404, CalendarNotFoundError),
        (410, CalendarNotFoundError),
        (409, CalendarConflictError),
        (503, CalendarProviderUnavailableError),
    ],
)
def test_cancel_event_wraps_http_errors(status, expected_error):
    events = _FakeEvents(error=_http_error(status))
    provider = GoogleCalendarProvider(service=_FakeService(events=events))

    with pytest.raises(expected_error):
        provider.cancel_event(calendar_id="primary", event_id="evt-1")


def test_cancel_event_wraps_google_auth_refresh_errors():
    """Found during live verification (DEC-032): a bad/revoked refresh token
    raises google.auth.exceptions.RefreshError *before* any HttpError is
    possible (it fails during googleapiclient's automatic token refresh, not
    the HTTP request itself) — HttpError-only wrapping missed this entirely."""
    from google.auth.exceptions import RefreshError

    events = _FakeEvents(error=RefreshError("invalid_grant: Token has been expired or revoked."))
    provider = GoogleCalendarProvider(service=_FakeService(events=events))

    with pytest.raises(CalendarAuthError):
        provider.cancel_event(calendar_id="primary", event_id="evt-1")


def test_provider_requires_credentials_or_service():
    with pytest.raises(ValueError):
        GoogleCalendarProvider()
