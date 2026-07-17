"""Tests for the onboarding API: business provisioning (Milestone A)."""

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import User

VALID_PAYLOAD = {
    "name": "Acme Dental Clinic",
    "owner_email": "owner@acmedental.com",
    "industry": "Dental Clinic",
    "contact_email": "hello@acmedental.com",
    "country": "India",
    "timezone": "Asia/Kolkata",
}


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def test_status_requires_authentication(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/onboarding/status")  # no Authorization header
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_status_rejects_invalid_token(db_session):
    def bad_verify(_token):
        raise HTTPException(status_code=401, detail="Invalid")

    client = _client(db_session, claims_for_token=bad_verify)
    resp = client.get("/api/v1/onboarding/status", headers=_auth())
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_status_has_no_business_for_new_clerk_user(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_new"})
    resp = client.get("/api/v1/onboarding/status", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["data"] == {"has_business": False, "business": None}
    app.dependency_overrides.clear()


def test_create_business_provisions_business_and_user(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_new"})

    resp = client.post("/api/v1/onboarding/business", json=VALID_PAYLOAD, headers=_auth())

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "Acme Dental Clinic"
    assert data["industry"] == "Dental Clinic"
    assert data["contact_email"] == "hello@acmedental.com"
    assert data["country"] == "India"
    assert data["timezone"] == "Asia/Kolkata"
    assert data["onboarding_status"] == "created"
    assert data["whatsapp_connection_status"] == "not_connected"

    user = db_session.query(User).filter_by(clerk_user_id="user_new").one()
    assert str(user.business_id) == data["id"]
    assert user.email == "owner@acmedental.com"
    assert user.role == "owner"
    app.dependency_overrides.clear()


def test_create_business_defaults_optional_fields(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_minimal"})

    resp = client.post(
        "/api/v1/onboarding/business",
        json={"name": "Minimal Biz", "owner_email": "owner@minimal.com"},
        headers=_auth(),
    )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["industry"] is None
    assert data["contact_email"] is None
    assert data["country"] is None
    assert data["timezone"] == "UTC"  # falls back to the Business model's default
    app.dependency_overrides.clear()


def test_create_business_rejects_blank_name(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_blank"})

    resp = client.post(
        "/api/v1/onboarding/business",
        json={"name": "   ", "owner_email": "owner@blank.com"},
        headers=_auth(),
    )

    assert resp.status_code == 422


def test_create_business_rejects_invalid_owner_email(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_bademail"})

    resp = client.post(
        "/api/v1/onboarding/business",
        json={"name": "Acme", "owner_email": "not-an-email"},
        headers=_auth(),
    )

    assert resp.status_code == 422


def test_create_business_rejects_invalid_timezone(db_session):
    # Regression: the onboarding form's timezone field is free text with no
    # frontend format check — the backend must reject an unrecognized IANA
    # key itself, matching app/api/calendar.py's existing validation, or a
    # bad value (e.g. "asia" instead of "Asia/Kolkata") gets stored and later
    # crashes every AI reply for that business (app/ai/prompts.py).
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_badtz"})

    resp = client.post(
        "/api/v1/onboarding/business",
        json={**VALID_PAYLOAD, "timezone": "asia"},
        headers=_auth(),
    )

    assert resp.status_code == 422


def test_create_business_rejects_oversized_name(db_session):
    # Regression: name had no max_length, and Business.name's own DB column
    # is String(255) — an oversized value used to fail at commit with a raw
    # DB error instead of a clean 422 (Sprint 52B, Task 2).
    from app.api.onboarding import MAX_NAME_LENGTH

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_oversized"})

    resp = client.post(
        "/api/v1/onboarding/business",
        json={**VALID_PAYLOAD, "name": "x" * (MAX_NAME_LENGTH + 1)},
        headers=_auth(),
    )

    assert resp.status_code == 422


def test_create_business_is_idempotent_for_same_clerk_user(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_twice"})

    first = client.post("/api/v1/onboarding/business", json=VALID_PAYLOAD, headers=_auth())
    second = client.post(
        "/api/v1/onboarding/business",
        json={**VALID_PAYLOAD, "name": "A Different Name"},
        headers=_auth(),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    assert second.json()["data"]["name"] == "Acme Dental Clinic"  # unchanged, not overwritten

    user_count = db_session.query(User).filter_by(clerk_user_id="user_twice").count()
    assert user_count == 1
    app.dependency_overrides.clear()


def test_status_reflects_business_after_provisioning(db_session):
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_flow"})
    client.post("/api/v1/onboarding/business", json=VALID_PAYLOAD, headers=_auth())

    resp = client.get("/api/v1/onboarding/status", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["has_business"] is True
    assert resp.json()["data"]["business"]["name"] == "Acme Dental Clinic"
    app.dependency_overrides.clear()
