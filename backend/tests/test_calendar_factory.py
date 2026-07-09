"""Tests for app/calendar/factory.py::get_appointment_service — resolving a
business's stored credentials + timezone/working_hours into a fully-wired
AppointmentService (DEC-032)."""

import pytest
from cryptography.fernet import Fernet

from app.calendar.credentials import store_credentials
from app.calendar.factory import get_appointment_service
from app.calendar.providers.base import CalendarNotConnectedError
from app.calendar.providers.google import GoogleCalendarProvider
from app.calendar.service import AppointmentService
from app.core.config import settings
from app.models import Business


@pytest.fixture(autouse=True)
def _calendar_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")


def test_get_appointment_service_raises_when_not_connected(db_session):
    biz = Business(name="Clinic A")
    db_session.add(biz)
    db_session.flush()

    with pytest.raises(CalendarNotConnectedError):
        get_appointment_service(db_session, biz.id)


def test_get_appointment_service_raises_for_unknown_business(db_session):
    import uuid

    with pytest.raises(CalendarNotConnectedError):
        get_appointment_service(db_session, uuid.uuid4())


def test_get_appointment_service_wires_provider_and_settings(db_session):
    biz = Business(
        name="Clinic A",
        timezone="America/New_York",
        working_hours={"mon": {"open": "09:00", "close": "17:00"}},
    )
    db_session.add(biz)
    db_session.flush()
    store_credentials(db_session, biz.id, "refresh-token", calendar_id="team-calendar")

    service = get_appointment_service(db_session, biz.id)

    assert isinstance(service, AppointmentService)
    assert isinstance(service._provider, GoogleCalendarProvider)
    assert service._calendar_id == "team-calendar"
    assert service._timezone == "America/New_York"
    assert service._working_hours == {"mon": {"open": "09:00", "close": "17:00"}}
