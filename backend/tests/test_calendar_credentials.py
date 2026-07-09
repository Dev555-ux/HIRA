"""Tests for app/calendar/credentials.py: store/get/disconnect and resolving a
stored CalendarCredential into a live google.oauth2.credentials.Credentials
object (DEC-032)."""

import pytest
from cryptography.fernet import Fernet

from app.calendar.credentials import (
    build_google_credentials,
    disconnect,
    get_google_credentials_for_business,
    get_stored_credential,
    store_credentials,
)
from app.calendar.providers.base import CalendarNotConnectedError
from app.core.config import settings
from app.models import Business, CalendarCredential


@pytest.fixture(autouse=True)
def _calendar_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")


def _business(db):
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    return biz


def test_store_credentials_creates_a_row(db_session):
    biz = _business(db_session)

    credential = store_credentials(db_session, biz.id, "refresh-token-1", calendar_id="primary")

    assert credential.business_id == biz.id
    assert credential.calendar_id == "primary"
    assert credential.refresh_token_encrypted != "refresh-token-1"  # encrypted at rest


def test_store_credentials_is_idempotent_per_business(db_session):
    biz = _business(db_session)
    store_credentials(db_session, biz.id, "refresh-token-1")

    store_credentials(db_session, biz.id, "refresh-token-2", calendar_id="secondary")

    rows = db_session.query(CalendarCredential).filter_by(business_id=biz.id).all()
    assert len(rows) == 1
    assert rows[0].calendar_id == "secondary"


def test_get_stored_credential_returns_none_when_not_connected(db_session):
    biz = _business(db_session)
    assert get_stored_credential(db_session, biz.id) is None


def test_disconnect_removes_the_row(db_session):
    biz = _business(db_session)
    store_credentials(db_session, biz.id, "refresh-token-1")

    assert disconnect(db_session, biz.id) is True
    assert get_stored_credential(db_session, biz.id) is None


def test_disconnect_returns_false_when_nothing_to_remove(db_session):
    biz = _business(db_session)
    assert disconnect(db_session, biz.id) is False


def test_build_google_credentials_decrypts_the_refresh_token(db_session):
    biz = _business(db_session)
    credential = store_credentials(db_session, biz.id, "the-real-refresh-token")

    google_credentials = build_google_credentials(credential)

    assert google_credentials.refresh_token == "the-real-refresh-token"
    assert google_credentials.client_id == "client-id"


def test_get_google_credentials_for_business_raises_when_not_connected(db_session):
    biz = _business(db_session)
    with pytest.raises(CalendarNotConnectedError):
        get_google_credentials_for_business(db_session, biz.id)


def test_get_google_credentials_for_business_is_tenant_scoped(db_session):
    biz_a = _business(db_session)
    biz_b = _business(db_session)
    store_credentials(db_session, biz_a.id, "refresh-token-a")

    with pytest.raises(CalendarNotConnectedError):
        get_google_credentials_for_business(db_session, biz_b.id)
