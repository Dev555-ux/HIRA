"""Tests for the Calendar API (/api/v1/calendar): auth, tenant isolation,
settings (timezone/working hours), OAuth connect/callback, status/disconnect,
and availability (DEC-032)."""

from urllib.parse import parse_qs, urlparse

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.calendar.credentials import get_stored_credential, store_credentials
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, User


def _seed_business(db, name, clerk_user_id, phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone)
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


def _configure_google(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(
        settings,
        "google_oauth_redirect_uri",
        "http://localhost:8000/api/v1/calendar/oauth/callback",
    )


# --- settings (timezone / working hours) -------------------------------------


def test_get_calendar_settings_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/calendar/settings")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_get_calendar_settings_returns_defaults(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/calendar/settings", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"timezone": "UTC", "working_hours": None}
    app.dependency_overrides.clear()


def test_patch_calendar_settings_updates_timezone(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        "/api/v1/calendar/settings", json={"timezone": "America/New_York"}, headers=_auth()
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["timezone"] == "America/New_York"
    db_session.refresh(biz)
    assert biz.timezone == "America/New_York"
    app.dependency_overrides.clear()


def test_patch_calendar_settings_updates_working_hours(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        "/api/v1/calendar/settings",
        json={"working_hours": {"mon": {"open": "09:00", "close": "17:00"}, "sun": None}},
        headers=_auth(),
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["working_hours"] == {
        "mon": {"open": "09:00", "close": "17:00"},
        "sun": None,
    }
    app.dependency_overrides.clear()


def test_patch_calendar_settings_rejects_invalid_timezone(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        "/api/v1/calendar/settings", json={"timezone": "Not/AZone"}, headers=_auth()
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_calendar_settings_rejects_invalid_time_format(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        "/api/v1/calendar/settings",
        json={"working_hours": {"mon": {"open": "9am", "close": "17:00"}}},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_calendar_settings_rejects_close_before_open(db_session):
    """Sprint 35 audit: nothing previously checked ordering, so a business
    could save backwards hours that would silently corrupt availability."""
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        "/api/v1/calendar/settings",
        json={"working_hours": {"mon": {"open": "17:00", "close": "09:00"}}},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_calendar_settings_rejects_unknown_day_key(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        "/api/v1/calendar/settings",
        json={"working_hours": {"funday": {"open": "09:00", "close": "17:00"}}},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_calendar_settings_rejects_empty_payload(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch("/api/v1/calendar/settings", json={}, headers=_auth())

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_calendar_settings_does_not_affect_another_business(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    client.patch(
        "/api/v1/calendar/settings", json={"timezone": "America/New_York"}, headers=_auth()
    )

    db_session.refresh(biz_b)
    assert biz_b.timezone == "UTC"
    app.dependency_overrides.clear()


# --- OAuth connect ------------------------------------------------------------


def test_oauth_connect_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/calendar/oauth/connect")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_oauth_connect_returns_authorization_url(db_session, monkeypatch):
    _configure_google(monkeypatch)
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/calendar/oauth/connect", headers=_auth())

    assert resp.status_code == 200
    assert "accounts.google.com" in resp.json()["data"]["authorization_url"]
    app.dependency_overrides.clear()


def test_oauth_connect_returns_503_when_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/calendar/oauth/connect", headers=_auth())

    assert resp.status_code == 503
    # Regression: this used to echo CalendarNotConfiguredError's own message
    # verbatim ("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/... are not set")
    # straight to the customer-facing toast. The detail must stay generic —
    # no env var names, no implementation details.
    detail = resp.json()["detail"]
    assert "GOOGLE_CLIENT_ID" not in detail
    assert "GOOGLE_CLIENT_SECRET" not in detail
    assert "GOOGLE_OAUTH_REDIRECT_URI" not in detail
    assert "CALENDAR_ENCRYPTION_KEY" not in detail
    assert detail == "Calendar integration hasn't been configured yet."
    app.dependency_overrides.clear()


# --- OAuth callback (public — no Clerk session) -------------------------------


def test_oauth_callback_stores_credentials_and_redirects_on_success(db_session, monkeypatch):
    _configure_google(monkeypatch)
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    monkeypatch.setattr(
        "app.api.calendar.oauth.exchange_code_for_refresh_token", lambda code: "a-refresh-token"
    )
    from app.calendar.oauth import sign_state

    client = TestClient(app)

    resp = client.get(
        f"/api/v1/calendar/oauth/callback?code=abc&state={sign_state(biz.id)}",
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["calendar"] == ["connected"]
    stored = get_stored_credential(db_session, biz.id)
    assert stored is not None
    app.dependency_overrides.clear()


def test_oauth_callback_redirects_with_error_on_google_error_param(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/api/v1/calendar/oauth/callback?error=access_denied", follow_redirects=False)

    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["calendar"] == ["error"]
    app.dependency_overrides.clear()


def test_oauth_callback_redirects_with_error_on_missing_code(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/api/v1/calendar/oauth/callback?state=whatever", follow_redirects=False)

    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["calendar"] == ["error"]
    app.dependency_overrides.clear()


def test_oauth_callback_redirects_with_error_on_invalid_state(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get(
        "/api/v1/calendar/oauth/callback?code=abc&state=forged", follow_redirects=False
    )

    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["calendar"] == ["error"]
    app.dependency_overrides.clear()


def test_oauth_callback_redirects_with_error_when_exchange_fails(db_session, monkeypatch):
    _configure_google(monkeypatch)
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session

    def _raise(code):
        from app.calendar.providers.base import CalendarAuthError

        raise CalendarAuthError("bad code")

    monkeypatch.setattr("app.api.calendar.oauth.exchange_code_for_refresh_token", _raise)
    from app.calendar.oauth import sign_state

    client = TestClient(app)

    resp = client.get(
        f"/api/v1/calendar/oauth/callback?code=abc&state={sign_state(biz.id)}",
        follow_redirects=False,
    )

    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["calendar"] == ["error"]
    assert get_stored_credential(db_session, biz.id) is None
    # Regression: this used to put str(exc) straight into the redirect URL's
    # `message` param — a raw underlying oauthlib/google-auth exception could
    # end up shown in the browser (Sprint 52B, Task 5).
    assert parse_qs(location.query)["message"] == [
        "Couldn't connect Google Calendar. Please try again."
    ]
    app.dependency_overrides.clear()


# --- status / disconnect ------------------------------------------------------


def test_get_calendar_status_not_connected(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/calendar/status", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"connected": False, "calendar_id": None}
    app.dependency_overrides.clear()


def test_get_calendar_status_connected(db_session, monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    store_credentials(db_session, biz.id, "refresh-token", calendar_id="primary")
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/calendar/status", headers=_auth())

    assert resp.json()["data"] == {"connected": True, "calendar_id": "primary"}
    app.dependency_overrides.clear()


def test_disconnect_calendar_removes_credentials(db_session, monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    store_credentials(db_session, biz.id, "refresh-token")
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.delete("/api/v1/calendar/disconnect", headers=_auth())

    assert resp.status_code == 204
    assert get_stored_credential(db_session, biz.id) is None
    app.dependency_overrides.clear()


def test_disconnect_calendar_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.delete("/api/v1/calendar/disconnect")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


# --- availability --------------------------------------------------------------


def test_get_availability_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(
        "/api/v1/calendar/availability?starts_at=2026-08-05T09:00:00&ends_at=2026-08-05T17:00:00"
    )
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_get_availability_succeeds_via_internal_scheduler_when_not_connected(db_session):
    """Sprint 78: no stored Google credential now falls back to
    InternalSchedulerProvider instead of failing — the whole window is free
    since no appointments exist yet for this business."""
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get(
        "/api/v1/calendar/availability?starts_at=2026-08-05T09:00:00&ends_at=2026-08-05T17:00:00",
        headers=_auth(),
    )

    assert resp.status_code == 200
    assert resp.json()["data"] == [
        {"starts_at": "2026-08-05T09:00:00Z", "ends_at": "2026-08-05T17:00:00Z"}
    ]
    app.dependency_overrides.clear()


def test_get_availability_rejects_ends_before_starts(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get(
        "/api/v1/calendar/availability?starts_at=2026-08-05T17:00:00&ends_at=2026-08-05T09:00:00",
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_get_availability_returns_slots_when_connected(db_session, monkeypatch):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    monkeypatch.setattr(
        "app.api.calendar.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get(
        "/api/v1/calendar/availability?starts_at=2026-08-05T09:00:00&ends_at=2026-08-05T17:00:00",
        headers=_auth(),
    )

    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
    app.dependency_overrides.clear()
