"""Tests for app/whatsapp/credentials.py: store/get/disconnect and the live
Graph API verification call (Sprint 69, self-serve WhatsApp connection)."""

import httpx
import pytest
from cryptography.fernet import Fernet

from app.models import Business, WhatsAppCredential
from app.whatsapp.credentials import (
    disconnect,
    get_access_token,
    get_app_secret,
    get_stored_credential,
    store_credentials,
    verify_whatsapp_credentials,
)
from app.whatsapp.errors import WhatsAppCredentialInvalidError
from app.core.config import settings


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _business(db):
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    return biz


def test_store_credentials_creates_a_row(db_session):
    biz = _business(db_session)

    credential = store_credentials(
        db_session, biz.id, access_token="token-1", app_secret="secret-1"
    )

    assert credential.business_id == biz.id
    assert credential.access_token_encrypted != "token-1"  # encrypted at rest
    assert credential.app_secret_encrypted != "secret-1"


def test_store_credentials_is_idempotent_per_business(db_session):
    biz = _business(db_session)
    store_credentials(db_session, biz.id, access_token="token-1", app_secret="secret-1")

    store_credentials(db_session, biz.id, access_token="token-2", app_secret="secret-2")

    rows = db_session.query(WhatsAppCredential).filter_by(business_id=biz.id).all()
    assert len(rows) == 1
    assert get_access_token(rows[0]) == "token-2"


def test_get_stored_credential_returns_none_when_not_connected(db_session):
    biz = _business(db_session)
    assert get_stored_credential(db_session, biz.id) is None


def test_disconnect_removes_the_row(db_session):
    biz = _business(db_session)
    store_credentials(db_session, biz.id, access_token="token-1", app_secret="secret-1")

    assert disconnect(db_session, biz.id) is True
    assert get_stored_credential(db_session, biz.id) is None


def test_disconnect_returns_false_when_nothing_to_remove(db_session):
    biz = _business(db_session)
    assert disconnect(db_session, biz.id) is False


def test_get_access_token_and_app_secret_decrypt_correctly(db_session):
    biz = _business(db_session)
    credential = store_credentials(
        db_session, biz.id, access_token="the-real-token", app_secret="the-real-secret"
    )

    assert get_access_token(credential) == "the-real-token"
    assert get_app_secret(credential) == "the-real-secret"


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_verify_whatsapp_credentials_succeeds_on_200_and_returns_the_display_phone_number():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer good-token"
        return httpx.Response(200, json={"display_phone_number": "+1 555 123 0000"})

    result = verify_whatsapp_credentials("PN1", "good-token", client=_client(handler))

    assert result == "+1 555 123 0000"


def test_verify_whatsapp_credentials_returns_none_if_meta_omits_the_field():
    """Degrades to "don't show a number" rather than raising — the field is
    always requested (fields=display_phone_number), so this shouldn't
    normally happen, but a missing field must never break the connect flow."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    result = verify_whatsapp_credentials("PN1", "good-token", client=_client(handler))

    assert result is None


def test_verify_whatsapp_credentials_raises_on_401():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid token"})

    with pytest.raises(WhatsAppCredentialInvalidError, match="access token"):
        verify_whatsapp_credentials("PN1", "bad-token", client=_client(handler))


def test_verify_whatsapp_credentials_raises_on_404():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "not found"})

    with pytest.raises(WhatsAppCredentialInvalidError, match="Phone Number ID"):
        verify_whatsapp_credentials("wrong-id", "good-token", client=_client(handler))


def test_verify_whatsapp_credentials_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    with pytest.raises(WhatsAppCredentialInvalidError, match="Could not reach"):
        verify_whatsapp_credentials("PN1", "good-token", client=_client(handler))
