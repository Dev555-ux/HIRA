"""Tests for the WhatsApp Embedded Signup API routes: feature-flag gating,
the stub provider's honest "not configured" behavior on an unconfigured
deployment, and the route contract once Tech Provider configuration is
present (Sprint 83). The flow itself is covered end to end against a mocked
Graph API in tests/test_embedded_signup_provider.py."""

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, User
from app.whatsapp.providers import get_embedded_signup_provider
from app.whatsapp.providers.embedded_signup_stub import StubEmbeddedSignupProvider


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


def test_routes_404_when_flag_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_embedded_signup", False)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    assert client.get("/api/v1/whatsapp/embedded-signup/config", headers=_auth()).status_code == 404
    assert client.post("/api/v1/whatsapp/embedded-signup/start", headers=_auth()).status_code == 404
    resp = client.post(
        "/api/v1/whatsapp/embedded-signup/callback",
        json={"code": "c", "state": "s"},
        headers=_auth(),
    )
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_config_reports_disabled_without_tech_provider_config_even_when_flag_on(
    db_session, monkeypatch
):
    """The flag alone doesn't make the flow available — Sprint 82 routes
    this through app/meta.py::tech_provider_configured(), so a deployment
    with the flag on but no Meta app configured still reports disabled and
    the frontend falls back to manual setup."""
    monkeypatch.setattr(settings, "enable_embedded_signup", True)
    monkeypatch.setattr(settings, "meta_app_id", "")
    monkeypatch.setattr(settings, "meta_app_secret", "")
    monkeypatch.setattr(settings, "meta_app_config_id", "")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/whatsapp/embedded-signup/config", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"enabled": False}
    app.dependency_overrides.clear()


def test_config_reports_enabled_once_tech_provider_config_is_complete(db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_embedded_signup", True)
    monkeypatch.setattr(settings, "meta_app_id", "898692016617650")
    monkeypatch.setattr(settings, "meta_app_secret", "a-real-app-secret")
    monkeypatch.setattr(settings, "meta_app_config_id", "a-real-config-id")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/whatsapp/embedded-signup/config", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"enabled": True}
    app.dependency_overrides.clear()


def test_start_returns_503_from_stub_provider_when_flag_on(db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_embedded_signup", True)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/whatsapp/embedded-signup/start", headers=_auth())

    assert resp.status_code == 503
    app.dependency_overrides.clear()


def test_callback_returns_503_from_stub_provider_when_flag_on(db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_embedded_signup", True)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/whatsapp/embedded-signup/callback",
        json={"code": "auth-code", "state": "some-state"},
        headers=_auth(),
    )

    assert resp.status_code == 503
    app.dependency_overrides.clear()


def test_factory_returns_stub_provider():
    assert isinstance(get_embedded_signup_provider(), StubEmbeddedSignupProvider)


def test_manual_connect_route_unaffected_by_flag(db_session, monkeypatch):
    """Track A guarantee: guided-manual v1's own routes don't consult the
    Embedded Signup flag at all — the manual provider is untouched."""
    monkeypatch.setattr(settings, "enable_embedded_signup", False)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/whatsapp/status", headers=_auth())

    assert resp.status_code == 200
    app.dependency_overrides.clear()


# --- Sprint 83: the route contract on a configured deployment -------------


def _configured(monkeypatch):
    monkeypatch.setattr(settings, "enable_embedded_signup", True)
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "meta_app_id", "898692016617650")
    monkeypatch.setattr(settings, "meta_app_secret", "stoneveil-app-secret")
    monkeypatch.setattr(settings, "meta_app_config_id", "config-abc")


def test_start_returns_the_config_id_and_a_fresh_state(db_session, monkeypatch):
    _configured(monkeypatch)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    first = client.post("/api/v1/whatsapp/embedded-signup/start", headers=_auth())
    second = client.post("/api/v1/whatsapp/embedded-signup/start", headers=_auth())

    assert first.status_code == 200
    assert first.json()["data"]["config_id"] == "config-abc"
    # A state per attempt, never reused — each is single-use downstream.
    assert first.json()["data"]["state"] != second.json()["data"]["state"]
    app.dependency_overrides.clear()


def test_callback_reports_a_bad_state_as_a_machine_readable_code(db_session, monkeypatch):
    """A rejected callback is a normal outcome, not a 5xx: 200 with an
    error_code the UI maps to its own copy."""
    _configured(monkeypatch)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/whatsapp/embedded-signup/callback",
        json={"code": "auth-code", "state": "not-a-real-state"},
        headers=_auth(),
    )

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["success"] is False
    assert body["error_code"] == "state_invalid"
    # No Meta prose, no scope names, no response bodies reach the client.
    assert "error" not in body
    app.dependency_overrides.clear()


def test_callback_rejects_an_oversized_meta_id(db_session, monkeypatch):
    _configured(monkeypatch)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/whatsapp/embedded-signup/callback",
        json={"code": "c", "state": "s", "waba_id": "9" * 65},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_start_reports_503_when_the_encryption_key_is_missing(db_session, monkeypatch):
    """No signing key means no state can be issued. That's a deployment
    gap, so it reports "unavailable" rather than surfacing as a 500."""
    _configured(monkeypatch)
    monkeypatch.setattr(settings, "calendar_encryption_key", "")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/whatsapp/embedded-signup/start", headers=_auth())

    assert resp.status_code == 503
    app.dependency_overrides.clear()
