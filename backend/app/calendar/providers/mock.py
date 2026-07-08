"""In-memory calendar provider for tests and local development.

Lets AppointmentService be exercised end-to-end with no real calendar vendor
(no OAuth, no network). Events live only in the instance's memory. Two
injectable behaviors support failure-path tests: `busy_windows` seeds existing
availability blockers, and `fail_with` makes every method raise that error
instead of executing.
"""

from __future__ import annotations

from dataclasses import replace

from app.calendar.providers.base import (
    CalendarError,
    CalendarEvent,
    CalendarEventDraft,
    CalendarEventUpdate,
    CalendarNotFoundError,
    CalendarConflictError,
    CalendarProvider,
    TimeSlot,
)


class MockCalendarProvider(CalendarProvider):
    def __init__(
        self,
        *,
        busy_windows: list[TimeSlot] | None = None,
        fail_with: type[CalendarError] | None = None,
    ):
        self._events: dict[str, CalendarEvent] = {}
        self._busy_windows = list(busy_windows or [])
        self._fail_with = fail_with
        self._next_id = 1

    def _maybe_fail(self) -> None:
        if self._fail_with is not None:
            raise self._fail_with("MockCalendarProvider configured to fail")

    def _overlaps_existing(self, starts_at, ends_at) -> bool:
        return any(
            e.status == "confirmed" and e.starts_at < ends_at and e.ends_at > starts_at
            for e in self._events.values()
        )

    def _overlaps_busy(self, window: TimeSlot) -> bool:
        return any(
            b.starts_at < window.ends_at and b.ends_at > window.starts_at for b in self._busy_windows
        )

    def get_availability(self, *, calendar_id: str, window: TimeSlot) -> list[TimeSlot]:
        self._maybe_fail()
        if self._overlaps_busy(window) or self._overlaps_existing(window.starts_at, window.ends_at):
            return []
        return [window]

    def create_event(self, *, calendar_id: str, draft: CalendarEventDraft) -> CalendarEvent:
        self._maybe_fail()
        window = TimeSlot(starts_at=draft.starts_at, ends_at=draft.ends_at)
        if self._overlaps_busy(window) or self._overlaps_existing(draft.starts_at, draft.ends_at):
            raise CalendarConflictError("Requested slot overlaps an existing event")

        event_id = f"mock-event-{self._next_id}"
        self._next_id += 1
        event = CalendarEvent(
            provider_event_id=event_id,
            starts_at=draft.starts_at,
            ends_at=draft.ends_at,
            status="confirmed",
        )
        self._events[event_id] = event
        return event

    def update_event(
        self, *, calendar_id: str, event_id: str, changes: CalendarEventUpdate
    ) -> CalendarEvent:
        self._maybe_fail()
        existing = self._events.get(event_id)
        if existing is None:
            raise CalendarNotFoundError(f"No event {event_id!r}")

        updated = replace(
            existing,
            starts_at=changes.starts_at or existing.starts_at,
            ends_at=changes.ends_at or existing.ends_at,
        )
        self._events[event_id] = updated
        return updated

    def cancel_event(self, *, calendar_id: str, event_id: str) -> None:
        self._maybe_fail()
        existing = self._events.get(event_id)
        if existing is None:
            raise CalendarNotFoundError(f"No event {event_id!r}")
        self._events[event_id] = replace(existing, status="cancelled")
