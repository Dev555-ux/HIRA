"""Tests for GET /health/instagram (Sprint 65 PR 7) — configuration/wiring
liveness for the Instagram channel. Mirrors tests/test_health_whatsapp.py's
shape; a deliberately different kind of check (no DB, no traffic signal —
see app/main.py::health_instagram's docstring for why)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _configure(monkeypatch, *, app_id="id", app_secret="secret", redirect_uri="https://x/callback"):
    monkeypatch.setattr(settings, "instagram_app_id", app_id)
    monkeypatch.setattr(settings, "instagram_app_secret", app_secret)
    monkeypatch.setattr(settings, "instagram_oauth_redirect_uri", redirect_uri)
    monkeypatch.setattr(settings, "calendar_encryption_key", "a-real-fernet-key")


def test_fully_configured_returns_200_with_every_check_true(db_session, monkeypatch):
    _configure(monkeypatch)
    client = _client(db_session)

    resp = client.get("/health/instagram")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"] == {
        "registry_contains_instagram": True,
        "provider_loads": True,
        "credential_encryption_available": True,
        "oauth_configured": True,
        "webhook_signing_configured": True,
    }
    app.dependency_overrides.clear()


def test_registry_and_provider_checks_pass_even_when_oauth_is_unconfigured(db_session, monkeypatch):
    """A WhatsApp-only deployment that has never configured Instagram OAuth
    is not "unhealthy" — the provider is still registered and loads fine;
    only the feature-specific checks report false."""
    monkeypatch.setattr(settings, "instagram_app_id", "")
    monkeypatch.setattr(settings, "instagram_app_secret", "")
    monkeypatch.setattr(settings, "instagram_oauth_redirect_uri", "")
    monkeypatch.setattr(settings, "calendar_encryption_key", "")
    client = _client(db_session)

    resp = client.get("/health/instagram")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["registry_contains_instagram"] is True
    assert body["checks"]["provider_loads"] is True
    assert body["checks"]["oauth_configured"] is False
    assert body["checks"]["webhook_signing_configured"] is False
    assert body["checks"]["credential_encryption_available"] is False
    app.dependency_overrides.clear()


def test_missing_provider_registration_returns_503(db_session, monkeypatch):
    """The one genuine failure case — the registry doesn't have Instagram
    at all (a code/registration bug, not a config choice). health_instagram()
    resolves via `ChannelManager()` with no registry override, which falls
    back to `app.services.channel_manager.get_default_registry()` — patch
    that name (not app.channels.registry's own copy) to match exactly what
    ChannelManager.__init__ actually calls."""
    from app.channels.registry import ChannelRegistry

    monkeypatch.setattr(
        "app.services.channel_manager.get_default_registry", lambda: ChannelRegistry()
    )
    client = _client(db_session)

    resp = client.get("/health/instagram")

    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["checks"]["registry_contains_instagram"] is False
    assert body["checks"]["provider_loads"] is False
    app.dependency_overrides.clear()


def test_never_touches_the_database(db_session, monkeypatch):
    """No DB query — patching get_db to a session that raises on any use
    would fail this test if health_instagram() ever touched it. Simpler
    proof: the endpoint takes no `db` dependency at all (see its
    signature) — this test documents that contract so a future change
    accidentally adding one gets caught by a full-suite regression, not
    silently."""
    import inspect

    from app.main import health_instagram

    assert "db" not in inspect.signature(health_instagram).parameters
