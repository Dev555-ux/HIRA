"""Calendar provider factory.

`get_calendar_provider()` returns a provider instance by name. Only "mock" is
registered today — Google/Outlook/CalDAV are added by implementing
`CalendarProvider` in this package and registering the class here, once their
credential-exchange logic exists (see app/calendar/credentials.py, not yet
built). No AppointmentService changes required.

Unlike `get_llm_provider`/`get_embedding_provider`, this factory is NOT cached:
those providers are stateless singletons configured from global settings, but
a real calendar provider (Google, etc.) will be constructed per-business with
that business's own credentials — caching by name alone would leak one
business's calendar client to another.
"""

from __future__ import annotations

from app.calendar.providers.base import CalendarError, CalendarProvider
from app.calendar.providers.mock import MockCalendarProvider

_PROVIDERS: dict[str, type[CalendarProvider]] = {
    "mock": MockCalendarProvider,
}


def get_calendar_provider(name: str) -> CalendarProvider:
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise CalendarError(f"Unknown calendar provider '{name}'. Known: {sorted(_PROVIDERS)}")
    return factory()


__all__ = ["CalendarError", "CalendarProvider", "get_calendar_provider"]
