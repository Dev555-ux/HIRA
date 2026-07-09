"""Calendar provider interface.

`AppointmentService` (app/calendar/service.py) depends only on this interface,
never on a concrete vendor. That lets Google/Outlook/CalDAV be added later by
implementing `CalendarProvider` and registering it in
app/calendar/providers/__init__.py — no changes to booking/reschedule/cancel
logic. Modeled after app/ai/llm/base.py's provider-abstraction shape.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class TimeSlot:
    starts_at: datetime
    ends_at: datetime


@dataclass
class CalendarEventDraft:
    starts_at: datetime
    ends_at: datetime
    summary: str
    description: str | None = None
    attendee_name: str | None = None


@dataclass
class CalendarEventUpdate:
    starts_at: datetime | None = None
    ends_at: datetime | None = None


@dataclass
class CalendarEvent:
    provider_event_id: str
    starts_at: datetime
    ends_at: datetime
    status: str  # confirmed | cancelled


class CalendarError(RuntimeError):
    """Base error for calendar provider failures."""


class CalendarAuthError(CalendarError):
    """Credentials are invalid/expired; the business must reconnect its calendar."""


class CalendarConflictError(CalendarError):
    """The requested slot is no longer free (a booking race)."""


class CalendarNotFoundError(CalendarError):
    """The referenced event does not exist (e.g. deleted externally)."""


class CalendarProviderUnavailableError(CalendarError):
    """Transient failure (network/5xx) — retryable."""


class CalendarNotConfiguredError(CalendarError):
    """Google OAuth client / encryption key isn't configured on this deployment."""


class CalendarNotConnectedError(CalendarError):
    """This business hasn't connected a calendar yet."""


class CalendarProvider(ABC):
    @abstractmethod
    def get_availability(self, *, calendar_id: str, window: TimeSlot) -> list[TimeSlot]:
        """Return the free sub-windows of `window` on this calendar."""

    @abstractmethod
    def create_event(self, *, calendar_id: str, draft: CalendarEventDraft) -> CalendarEvent:
        """Create an event. Raises CalendarConflictError if the slot isn't free."""

    @abstractmethod
    def update_event(
        self, *, calendar_id: str, event_id: str, changes: CalendarEventUpdate
    ) -> CalendarEvent:
        """Reschedule an existing event. Raises CalendarNotFoundError if it's gone."""

    @abstractmethod
    def cancel_event(self, *, calendar_id: str, event_id: str) -> None:
        """Cancel an existing event. Raises CalendarNotFoundError if it's gone."""
