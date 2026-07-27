"""Google Calendar implementation of CalendarProvider (DEC-032).

Maps the interface's four methods onto the Calendar API v3's `freebusy` and
`events` resources. `HttpError`s are translated into the existing
`CalendarError` hierarchy so callers (AppointmentService, the AI tool
dispatcher) never need to know this is Google specifically.

The underlying API `service` resource is injectable (matching
`app/services/messaging.py`'s injectable-httpx-client convention) so tests
can exercise this against a fake without any network access or real
credentials.
"""

from __future__ import annotations

from datetime import datetime

from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.calendar.providers.base import (
    CalendarAuthError,
    CalendarConflictError,
    CalendarError,
    CalendarEvent,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarNotFoundError,
    CalendarProvider,
    CalendarProviderUnavailableError,
    TimeSlot,
    invert_busy_periods,
)


def _to_rfc3339(value: datetime) -> str:
    return value.isoformat()


def _parse_rfc3339(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _to_calendar_event(raw: dict) -> CalendarEvent:
    return CalendarEvent(
        provider_event_id=raw["id"],
        starts_at=_parse_rfc3339(raw["start"]["dateTime"]),
        ends_at=_parse_rfc3339(raw["end"]["dateTime"]),
        status="cancelled" if raw.get("status") == "cancelled" else "confirmed",
    )


def _wrap_error(exc: HttpError | GoogleAuthError) -> CalendarError:
    if isinstance(exc, GoogleAuthError):
        # Raised by google-auth *before* a request reaches Google's HTTP API,
        # when the stored refresh token is invalid/revoked (googleapiclient's
        # request wrapper calls Credentials.refresh() ahead of every call) —
        # a real gap found during live verification (DEC-032): HttpError
        # alone doesn't cover this.
        return CalendarAuthError(f"Google Calendar authorization failed: {exc}")
    status = exc.resp.status if exc.resp is not None else None
    if status in (401, 403):
        return CalendarAuthError(f"Google Calendar authorization failed: {exc}")
    if status in (404, 410):
        return CalendarNotFoundError(f"Google Calendar event not found: {exc}")
    if status == 409:
        return CalendarConflictError(f"Google Calendar conflict: {exc}")
    if status is not None and status >= 500:
        return CalendarProviderUnavailableError(f"Google Calendar unavailable: {exc}")
    return CalendarError(f"Google Calendar request failed: {exc}")


class GoogleCalendarProvider(CalendarProvider):
    def __init__(self, credentials: Credentials | None = None, *, service=None):
        if service is not None:
            self._service = service
        elif credentials is not None:
            self._service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        else:
            raise ValueError("GoogleCalendarProvider requires credentials or an injected service")

    def _get_busy_periods(self, calendar_id: str, window: TimeSlot) -> list[TimeSlot]:
        body = {
            "timeMin": _to_rfc3339(window.starts_at),
            "timeMax": _to_rfc3339(window.ends_at),
            "items": [{"id": calendar_id}],
        }
        try:
            response = self._service.freebusy().query(body=body).execute()
        except (HttpError, GoogleAuthError) as exc:
            raise _wrap_error(exc) from exc
        busy_raw = response.get("calendars", {}).get(calendar_id, {}).get("busy", [])
        return [
            TimeSlot(starts_at=_parse_rfc3339(b["start"]), ends_at=_parse_rfc3339(b["end"]))
            for b in busy_raw
        ]

    def get_availability(self, *, calendar_id: str, window: TimeSlot) -> list[TimeSlot]:
        busy = self._get_busy_periods(calendar_id, window)
        return invert_busy_periods(window, busy)

    def create_event(self, *, calendar_id: str, draft: CalendarEventDraft) -> CalendarEvent:
        window = TimeSlot(starts_at=draft.starts_at, ends_at=draft.ends_at)
        if self._get_busy_periods(calendar_id, window):
            # Google's API does not reject overlapping events on its own —
            # this pre-check is what gives create_event its documented
            # "raises CalendarConflictError if the slot isn't free" contract.
            raise CalendarConflictError("Requested slot overlaps an existing event")

        description = draft.description or ""
        if draft.attendee_name:
            description = f"{description}\nBooked for: {draft.attendee_name}".strip()

        body = {
            "summary": draft.summary,
            "description": description or None,
            "start": {"dateTime": _to_rfc3339(draft.starts_at)},
            "end": {"dateTime": _to_rfc3339(draft.ends_at)},
        }
        try:
            event = self._service.events().insert(calendarId=calendar_id, body=body).execute()
        except (HttpError, GoogleAuthError) as exc:
            raise _wrap_error(exc) from exc
        return _to_calendar_event(event)

    def update_event(
        self, *, calendar_id: str, event_id: str, changes: CalendarEventUpdate
    ) -> CalendarEvent:
        body = {}
        if changes.starts_at is not None:
            body["start"] = {"dateTime": _to_rfc3339(changes.starts_at)}
        if changes.ends_at is not None:
            body["end"] = {"dateTime": _to_rfc3339(changes.ends_at)}
        try:
            event = (
                self._service.events()
                .patch(calendarId=calendar_id, eventId=event_id, body=body)
                .execute()
            )
        except (HttpError, GoogleAuthError) as exc:
            raise _wrap_error(exc) from exc
        return _to_calendar_event(event)

    def cancel_event(self, *, calendar_id: str, event_id: str) -> None:
        try:
            self._service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        except (HttpError, GoogleAuthError) as exc:
            raise _wrap_error(exc) from exc
