"""Tests for app/main.py: CORS configuration (Sprint 34) and the global
unhandled-exception handler (Sprint 36)."""

import logging

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.main import app


def test_frontend_url_is_an_allowed_cors_origin():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": settings.frontend_url})

    assert response.headers.get("access-control-allow-origin") == settings.frontend_url


def test_dev_localhost_origins_remain_allowed():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_an_unrecognized_origin_is_not_allowed():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers


def test_unhandled_exception_returns_generic_500_and_is_logged(db_session, caplog):
    """A genuinely unhandled exception (not an HTTPException any route
    raises on purpose) must not leak internal detail to the client, and must
    be logged — previously invisible: Starlette's default 500 handler logs
    nothing at the application level."""

    def _boom(_token):
        raise RuntimeError("simulated auth backend failure")

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: _boom
    # raise_server_exceptions=False: TestClient's default re-raises exceptions
    # in the test process for debugging visibility even when a registered
    # handler already produced a response — opt out to assert on that
    # response, which is what a real client over the network actually sees.
    client = TestClient(app, raise_server_exceptions=False)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        resp = client.get("/api/v1/leads", headers={"Authorization": "Bearer tok"})

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert "simulated auth backend failure" not in resp.text
    assert any(
        "Unhandled exception" in record.message and "/api/v1/leads" in record.message
        for record in caplog.records
    )
    app.dependency_overrides.clear()


def test_http_exceptions_are_unaffected_by_the_global_handler(db_session):
    """A route's own HTTPException (e.g. 401 for a missing token) must still
    come through as-is — the catch-all only fires for truly unhandled
    exceptions."""
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/api/v1/leads")  # no Authorization header -> 401

    assert resp.status_code == 401
    assert resp.json()["detail"] == "Missing bearer token"
    app.dependency_overrides.clear()
