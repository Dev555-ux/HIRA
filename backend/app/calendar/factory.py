"""Resolves a fully-wired AppointmentService for a business: loads its stored
Google credentials, builds a GoogleCalendarProvider, and reads its
timezone/working_hours — the one place real (non-Mock) calendar wiring
happens. `get_calendar_provider()` (providers/__init__.py) stays mock-only on
purpose (see its docstring); a real provider needs per-business credentials,
which only this factory has access to.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.calendar.credentials import build_google_credentials, get_stored_credential
from app.calendar.providers.base import CalendarNotConnectedError
from app.calendar.providers.google import GoogleCalendarProvider
from app.calendar.service import AppointmentService
from app.models import Business


def get_appointment_service(db: Session, business_id: uuid.UUID) -> AppointmentService:
    """Raises CalendarNotConnectedError if this business hasn't connected a
    Google Calendar yet."""
    business = db.get(Business, business_id)
    stored = get_stored_credential(db, business_id)
    if business is None or stored is None:
        raise CalendarNotConnectedError("This business has not connected a Google Calendar")

    provider = GoogleCalendarProvider(build_google_credentials(stored))
    return AppointmentService(
        db,
        business_id,
        provider,
        stored.calendar_id or "primary",
        timezone=business.timezone,
        working_hours=business.working_hours,
    )
