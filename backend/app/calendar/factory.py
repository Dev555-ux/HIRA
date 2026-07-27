"""Resolves a fully-wired AppointmentService for a business — the one place
real (non-Mock) calendar provider selection happens. `get_calendar_provider()`
(providers/__init__.py) stays mock-only on purpose (see its docstring); a
real provider needs per-business credentials, which only this factory has
access to.

Sprint 78/79: a business with no stored Google credential is scheduled by
InternalSchedulerProvider — internally "HIRA Calendar," the product's own
always-on scheduling system (Sprint 79 promoted this from a stopgap fallback
to the default, first-class experience; the class name itself stays an
internal implementation detail, never customer-facing). No Google OAuth
setup is required for scheduling to work end-to-end. The moment a business
connects Google Calendar (the existing OAuth flow, unchanged) as an optional
sync layer, `get_stored_credential` starts returning a row again and this
function resumes wiring GoogleCalendarProvider automatically — no other code
needs to know or care which provider is active.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.calendar.credentials import build_google_credentials, get_stored_credential
from app.calendar.providers.base import CalendarNotConnectedError, CalendarProvider
from app.calendar.providers.google import GoogleCalendarProvider
from app.calendar.providers.internal import InternalSchedulerProvider
from app.calendar.service import AppointmentService
from app.models import Business


def get_appointment_service(db: Session, business_id: uuid.UUID) -> AppointmentService:
    """Raises CalendarNotConnectedError only if `business_id` itself doesn't
    exist — a business with no connected Google Calendar now gets a working,
    internally-scheduled AppointmentService instead of an error."""
    business = db.get(Business, business_id)
    if business is None:
        raise CalendarNotConnectedError("This business has not connected a Google Calendar")

    stored = get_stored_credential(db, business_id)
    provider: CalendarProvider
    if stored is not None:
        provider = GoogleCalendarProvider(build_google_credentials(stored))
        calendar_id = stored.calendar_id or "primary"
    else:
        provider = InternalSchedulerProvider(db, business_id)
        calendar_id = "internal"

    return AppointmentService(
        db,
        business_id,
        provider,
        calendar_id,
        timezone=business.timezone,
        working_hours=business.working_hours,
    )
