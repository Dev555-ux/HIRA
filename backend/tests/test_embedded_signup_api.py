"""Tests for the WhatsApp Embedded Signup placeholder API (Track B prep,
TODOS.md ONBOARD-E): feature-flag gating and the stub provider's honest
"not configured" behavior. No real Meta call exists yet to test against."""

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


def test_config_reports_disabled_without_config_id_even_when_flag_on(db_session, monkeypatch):
    monkeypatch.setattr(settings, "enable_embedded_signup", True)
    monkeypatch.setattr(settings, "embedded_signup_config_id", "")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/whatsapp/embedded-signup/config", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"enabled": False}
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
