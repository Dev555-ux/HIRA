"""Tests for the Appointments API (/api/v1/appointments): auth, tenant
isolation, CRUD/actions, and CalendarError mapping — always via
AppointmentService (get_appointment_service monkeypatched to a Mock-backed
instance; there is no local-only appointment path) (DEC-032)."""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth.dependencies import get_token_verifier
from app.calendar.providers.base import CalendarEventDraft
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.db.session import get_db
from app.main import app
from app.models import Appointment, Business, Customer, User
from tests.conftest import TEST_DATABASE_URL

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def _seed_business(db, name, clerk_user_id, phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone)
    db.add(biz)
    db.flush()
    user = User(business_id=biz.id, clerk_user_id=clerk_user_id, email=f"{name}@x.com")
    db.add(user)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    return biz, user, customer


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def _mock_service(monkeypatch, provider=None):
    # Resolve the provider once, outside the lambda — the real calendar's
    # state persists across requests, so the fake must too, or a create
    # followed by a reschedule/cancel would hit a fresh, empty provider.
    provider = provider or MockCalendarProvider()
    monkeypatch.setattr(
        "app.api.appointments.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, provider, calendar_id="primary"
        ),
    )


# --- create ------------------------------------------------------------------


def test_create_appointment_requires_authentication(db_session):
    biz, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
    )
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_create_appointment_books_via_appointment_service(db_session, monkeypatch):
    biz, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["status"] == "booked"
    assert data["customer"]["wa_phone"] == "+15551230000"
    app.dependency_overrides.clear()


def test_create_appointment_rejects_oversized_summary(db_session, monkeypatch):
    # Regression: summary had no max_length — Sprint 52B, Task 2.
    from app.api.appointments import MAX_SUMMARY_LENGTH

    biz, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "x" * (MAX_SUMMARY_LENGTH + 1),
        },
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_create_appointment_durably_commits_independent_of_caller(db_session, monkeypatch):
    """Section A4: book_appointment's default commit=True must remain the
    sole thing that persists a REST-created appointment, exactly as before
    -- proven via a genuinely separate connection, not just the same
    session the request and this test share via the get_db override."""
    biz, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    )
    assert resp.status_code == 201
    appointment_id = uuid.UUID(resp.json()["data"]["id"])
    app.dependency_overrides.clear()

    verify_session = sessionmaker(bind=create_engine(TEST_DATABASE_URL))()
    try:
        appointment = verify_session.get(Appointment, appointment_id)
        assert appointment is not None
        assert appointment.status == "booked"
    finally:
        verify_session.close()


def test_create_appointment_rejects_unknown_customer(db_session, monkeypatch):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_create_appointment_rejects_ends_before_starts(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": (NOW + timedelta(hours=1)).isoformat(),
            "ends_at": NOW.isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_create_appointment_returns_409_when_calendar_not_connected(db_session):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    )

    assert resp.status_code == 409
    app.dependency_overrides.clear()


def test_create_appointment_returns_409_on_conflict(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    busy = MockCalendarProvider()
    busy.create_event(
        calendar_id="primary",
        draft=CalendarEventDraft(
            starts_at=NOW, ends_at=NOW + timedelta(hours=1), summary="Existing"
        ),
    )
    _mock_service(monkeypatch, provider=busy)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Double booked",
        },
        headers=_auth(),
    )

    assert resp.status_code == 409
    app.dependency_overrides.clear()


def test_create_appointment_for_another_businesss_customer_is_404(db_session, monkeypatch):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    _, _, customer_b = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer_b.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- list / get ----------------------------------------------------------------


def test_list_appointments_is_tenant_scoped(db_session, monkeypatch):
    _, _, customer_a = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _, customer_b = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()
    _mock_service(monkeypatch)
    client_a = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client_a.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer_a.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "A's appointment",
        },
        headers=_auth(),
    )
    app.dependency_overrides.clear()
    client_b = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    client_b.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer_b.id),
            "starts_at": (NOW + timedelta(hours=5)).isoformat(),
            "ends_at": (NOW + timedelta(hours=6)).isoformat(),
            "summary": "B's appointment",
        },
        headers=_auth(),
    )
    app.dependency_overrides.clear()

    client_a = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client_a.get("/api/v1/appointments", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["wa_phone"] == "+15551230000"
    app.dependency_overrides.clear()


def test_list_appointments_filters_by_date_range(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Soon",
        },
        headers=_auth(),
    )
    later = NOW + timedelta(days=10)
    client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": later.isoformat(),
            "ends_at": (later + timedelta(hours=1)).isoformat(),
            "summary": "Later",
        },
        headers=_auth(),
    )

    resp = client.get(
        "/api/v1/appointments",
        params={"from": NOW.isoformat(), "to": (NOW + timedelta(days=1)).isoformat()},
        headers=_auth(),
    )

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert len(data) == 1
    # starts_at is a naive TIMESTAMP column (matches the rest of the schema —
    # see test_appointment_service.py) — Sprint 77: serialized via
    # to_iso_utc, which re-marks that naive-but-UTC value with an explicit
    # "Z" rather than leaving it ambiguous.
    assert data[0]["starts_at"] == NOW.isoformat().replace("+00:00", "Z")
    assert body["meta"] == {"total": 1, "limit": 200, "offset": 0}
    app.dependency_overrides.clear()


def test_list_appointments_supports_limit_and_offset(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    for i in range(4):
        starts = NOW + timedelta(hours=i)
        client.post(
            "/api/v1/appointments",
            json={
                "customer_id": str(customer.id),
                "starts_at": starts.isoformat(),
                "ends_at": (starts + timedelta(minutes=30)).isoformat(),
                "summary": f"Appt {i}",
            },
            headers=_auth(),
        )

    resp = client.get("/api/v1/appointments", params={"limit": 2, "offset": 1}, headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 4, "limit": 2, "offset": 1}
    app.dependency_overrides.clear()


def test_get_appointment_requires_authentication(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    created = client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer.id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    ).json()["data"]
    app.dependency_overrides.clear()

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(f"/api/v1/appointments/{created['id']}")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_get_unknown_appointment_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/appointments/00000000-0000-0000-0000-000000000000", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- reschedule / cancel -------------------------------------------------------


def _create_appointment(client, customer_id):
    return client.post(
        "/api/v1/appointments",
        json={
            "customer_id": str(customer_id),
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
            "summary": "Cleaning",
        },
        headers=_auth(),
    ).json()["data"]


def test_reschedule_appointment(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    appointment = _create_appointment(client, customer.id)

    new_starts_at = NOW + timedelta(hours=5)
    new_ends_at = new_starts_at + timedelta(hours=1)
    resp = client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule",
        json={"starts_at": new_starts_at.isoformat(), "ends_at": new_ends_at.isoformat()},
        headers=_auth(),
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rescheduled"
    app.dependency_overrides.clear()


def test_reschedule_rejects_ends_before_starts(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    appointment = _create_appointment(client, customer.id)

    resp = client.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule",
        json={"starts_at": NOW.isoformat(), "ends_at": (NOW - timedelta(hours=1)).isoformat()},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_reschedule_unknown_appointment_is_404(db_session, monkeypatch):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/appointments/00000000-0000-0000-0000-000000000000/reschedule",
        json={"starts_at": NOW.isoformat(), "ends_at": (NOW + timedelta(hours=1)).isoformat()},
        headers=_auth(),
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_cancel_appointment(db_session, monkeypatch):
    _, _, customer = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_service(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    appointment = _create_appointment(client, customer.id)

    resp = client.post(f"/api/v1/appointments/{appointment['id']}/cancel", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "cancelled"
    app.dependency_overrides.clear()


def test_cannot_reschedule_another_businesss_appointment(db_session, monkeypatch):
    _, _, customer_a = _seed_business(db_session, "A", "user_a", phone="PN_A")
    _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()
    _mock_service(monkeypatch)
    client_a = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    appointment = _create_appointment(client_a, customer_a.id)
    app.dependency_overrides.clear()

    _mock_service(monkeypatch)
    client_b = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    resp = client_b.post(
        f"/api/v1/appointments/{appointment['id']}/reschedule",
        json={
            "starts_at": (NOW + timedelta(hours=5)).isoformat(),
            "ends_at": (NOW + timedelta(hours=6)).isoformat(),
        },
        headers=_auth(),
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()
