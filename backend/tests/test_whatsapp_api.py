"""Tests for the WhatsApp API (/api/v1/whatsapp): connect/status/disconnect
(Sprint 69, self-serve "guided-manual v1" connection)."""

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, User
from app.whatsapp.credentials import get_stored_credential, store_credentials
from app.whatsapp.errors import WhatsAppCredentialInvalidError


def _seed_business(db, name, clerk_user_id):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    user = User(business_id=biz.id, clerk_user_id=clerk_user_id, email=f"{name}@x.com")
    db.add(user)
    db.flush()
    return biz, user


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def _configure_encryption(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


CONNECT_BODY = {
    "phone_number_id": "1234567890",
    "whatsapp_business_account_id": "waba-1",
    "access_token": "real-access-token",
    "app_secret": "real-app-secret",
}


def test_get_status_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/whatsapp/status")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_get_status_when_not_connected(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/whatsapp/status", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "connected": False,
        "status": "not_connected",
        "phone_number_id_masked": None,
        "connected_at": None,
    }
    app.dependency_overrides.clear()


def test_connect_verifies_credentials_before_storing(db_session, monkeypatch):
    _configure_encryption(monkeypatch)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    calls = []
    monkeypatch.setattr(
        "app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials",
        lambda phone_number_id, access_token: calls.append((phone_number_id, access_token)),
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["connected"] is True
    assert data["status"] == "connected"
    assert data["phone_number_id_masked"] == "••••7890"
    assert data["connected_at"] is not None
    assert calls == [("1234567890", "real-access-token")]
    app.dependency_overrides.clear()


def test_connect_persists_business_fields_and_encrypted_credential(db_session, monkeypatch):
    _configure_encryption(monkeypatch)
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    monkeypatch.setattr(
        "app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials", lambda *a, **k: None
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    client.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    db_session.refresh(biz)
    assert biz.whatsapp_phone_number_id == "1234567890"
    assert biz.whatsapp_business_account_id == "waba-1"
    assert biz.whatsapp_connection_status == "connected"
    credential = get_stored_credential(db_session, biz.id)
    assert credential is not None
    assert credential.access_token_encrypted != "real-access-token"  # encrypted at rest
    app.dependency_overrides.clear()


def test_connect_rejects_invalid_credentials_without_storing_anything(db_session, monkeypatch):
    _configure_encryption(monkeypatch)
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()

    def _fail(phone_number_id, access_token):
        raise WhatsAppCredentialInvalidError(
            "Meta rejected the access token — check you copied it."
        )

    monkeypatch.setattr("app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials", _fail)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    assert resp.status_code == 422
    assert "access token" in resp.json()["detail"]
    db_session.refresh(biz)
    assert biz.whatsapp_connection_status == "not_connected"
    assert get_stored_credential(db_session, biz.id) is None
    app.dependency_overrides.clear()


def test_connect_is_idempotent_and_doubles_as_reconnect(db_session, monkeypatch):
    _configure_encryption(monkeypatch)
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    monkeypatch.setattr(
        "app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials", lambda *a, **k: None
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    reconnect_body = {**CONNECT_BODY, "access_token": "new-access-token"}
    resp = client.post("/api/v1/whatsapp/connect", json=reconnect_body, headers=_auth())

    assert resp.status_code == 200
    rows = (
        db_session.query(type(get_stored_credential(db_session, biz.id)))
        .filter_by(business_id=biz.id)
        .all()
    )
    assert len(rows) == 1  # replaced, not duplicated
    app.dependency_overrides.clear()


def test_disconnect_clears_credential_and_business_fields(db_session, monkeypatch):
    _configure_encryption(monkeypatch)
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.flush()
    store_credentials(db_session, biz.id, access_token="tok", app_secret="sec")
    biz.whatsapp_phone_number_id = "1234567890"
    biz.whatsapp_business_account_id = "waba-1"
    biz.whatsapp_connection_status = "connected"
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/whatsapp/disconnect", headers=_auth())

    assert resp.status_code == 204
    db_session.refresh(biz)
    assert biz.whatsapp_phone_number_id is None
    assert biz.whatsapp_business_account_id is None
    assert biz.whatsapp_connection_status == "not_connected"
    assert get_stored_credential(db_session, biz.id) is None
    app.dependency_overrides.clear()


def test_disconnect_is_a_no_op_when_never_connected(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/whatsapp/disconnect", headers=_auth())

    assert resp.status_code == 204
    app.dependency_overrides.clear()


def test_connect_rejects_phone_number_already_connected_to_another_business(
    db_session, monkeypatch
):
    _configure_encryption(monkeypatch)
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    db_session.commit()
    monkeypatch.setattr(
        "app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials", lambda *a, **k: None
    )
    client_a = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp_a = client_a.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())
    assert resp_a.status_code == 200
    app.dependency_overrides.clear()

    client_b = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    resp_b = client_b.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    assert resp_b.status_code == 409
    assert "already connected" in resp_b.json()["detail"]
    db_session.refresh(biz_b)
    assert biz_b.whatsapp_phone_number_id is None
    assert biz_b.whatsapp_connection_status == "not_connected"
    assert get_stored_credential(db_session, biz_b.id) is None  # no orphaned credential
    db_session.refresh(biz_a)
    assert biz_a.whatsapp_phone_number_id == "1234567890"  # business A untouched
    app.dependency_overrides.clear()


def test_connect_allows_reconnecting_own_phone_number(db_session, monkeypatch):
    """The uniqueness check excludes the caller's own business — a business
    reconnecting/re-verifying the same number it already owns is not a
    conflict with itself."""
    _configure_encryption(monkeypatch)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    monkeypatch.setattr(
        "app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials", lambda *a, **k: None
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    resp = client.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())

    assert resp.status_code == 200
    app.dependency_overrides.clear()


def test_businesses_whatsapp_phone_number_id_has_db_level_unique_constraint(db_session):
    """Defense-in-depth: even bypassing the API's app-layer check entirely
    (e.g. two requests racing past it concurrently), the database itself
    refuses a second business row with the same phone_number_id."""
    biz_a = Business(name="A", whatsapp_phone_number_id="1234567890")
    db_session.add(biz_a)
    db_session.commit()

    biz_b = Business(name="B", whatsapp_phone_number_id="1234567890")
    db_session.add(biz_b)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_businesses_can_share_unconnected_null_phone_number_id(db_session):
    """The unique index is partial (WHERE NOT NULL) — many never-connected
    businesses coexist fine."""
    db_session.add(Business(name="A"))
    db_session.add(Business(name="B"))
    db_session.commit()  # does not raise


def test_status_and_connect_are_tenant_scoped(db_session, monkeypatch):
    _configure_encryption(monkeypatch)
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    db_session.commit()
    monkeypatch.setattr(
        "app.api.whatsapp.whatsapp_credentials.verify_whatsapp_credentials", lambda *a, **k: None
    )
    client_a = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client_a.post("/api/v1/whatsapp/connect", json=CONNECT_BODY, headers=_auth())
    app.dependency_overrides.clear()

    client_b = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    resp = client_b.get("/api/v1/whatsapp/status", headers=_auth())

    assert resp.json()["data"]["connected"] is False  # business B unaffected
    assert get_stored_credential(db_session, biz_b.id) is None
    app.dependency_overrides.clear()
