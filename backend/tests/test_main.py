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
    assert resp.json() == {"detail": "Something went wrong. Please try again."}
    assert "simulated auth backend failure" not in resp.text
    assert any(
        "Unhandled exception" in record.message and "/api/v1/leads" in record.message
        for record in caplog.records
    )
    app.dependency_overrides.clear()


def test_unhandled_exception_is_captured_by_error_monitoring(db_session, monkeypatch):
    # Regression: Sentry (app/core/monitoring.py) must see every exception
    # this handler catches, not just log it (Sprint 52B, Task 3).
    captured = []
    monkeypatch.setattr("app.main.capture_exception", captured.append)

    def _boom(_token):
        raise RuntimeError("simulated auth backend failure")

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: _boom
    client = TestClient(app, raise_server_exceptions=False)

    client.get("/api/v1/leads", headers={"Authorization": "Bearer tok"})

    assert len(captured) == 1
    assert isinstance(captured[0], RuntimeError)
    app.dependency_overrides.clear()


def test_response_includes_request_id_header(db_session):
    # Sprint 52B, Task 4 — every response carries a request ID a bug report
    # can reference, whether or not the caller sent one.
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/health")

    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0
    app.dependency_overrides.clear()


def test_incoming_request_id_is_reused_not_replaced(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/health", headers={"X-Request-ID": "my-own-id-123"})

    assert resp.headers["X-Request-ID"] == "my-own-id-123"
    app.dependency_overrides.clear()


def test_request_is_logged_with_request_id_status_and_duration(db_session, caplog):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger="app.request"):
        resp = client.get("/health")

    request_id = resp.headers["X-Request-ID"]
    matching = [r for r in caplog.records if request_id in r.message]
    assert len(matching) == 1
    line = matching[0].message
    assert "method=GET" in line
    assert "path=/health" in line
    assert "status=200" in line
    assert "duration_ms=" in line
    app.dependency_overrides.clear()


def test_authenticated_request_log_includes_business_id(db_session, caplog):
    from app.models import Business, User

    biz = Business(name="A")
    db_session.add(biz)
    db_session.flush()
    user = User(business_id=biz.id, clerk_user_id="user_a", email="a@x.com")
    db_session.add(user)
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda t: {"sub": "user_a"}
    client = TestClient(app)

    with caplog.at_level(logging.INFO, logger="app.request"):
        resp = client.get("/api/v1/leads", headers={"Authorization": "Bearer tok"})

    request_id = resp.headers["X-Request-ID"]
    matching = [r for r in caplog.records if request_id in r.message]
    assert len(matching) == 1
    assert f"business_id={biz.id}" in matching[0].message
    app.dependency_overrides.clear()


def test_pydantic_validation_error_detail_is_a_plain_string(db_session, monkeypatch):
    # Regression: FastAPI's default RequestValidationError handler returns
    # `detail` as a *list* of error dicts. Every other error in this app
    # returns `detail` as a string, and the frontend's error banner
    # (frontend/src/app/(dashboard)/demo/page.tsx) renders it directly —
    # coercing a list of objects to a string prints the literal text
    # "[object Object]" in the UI (Sprint 52B, Task 2/5).
    from app.models import Business, User

    biz = Business(name="A")
    db_session.add(biz)
    db_session.flush()
    user = User(business_id=biz.id, clerk_user_id="user_a", email="a@x.com")
    db_session.add(user)
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda t: {"sub": "user_a"}
    client = TestClient(app)

    resp = client.post(
        "/api/v1/onboarding/playground/message",
        headers={"Authorization": "Bearer tok"},
        json={"message": "x" * 5000},
    )

    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert isinstance(detail, str)
    assert "[object Object]" not in detail
    assert "message" in detail
    assert "4096" in detail
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
