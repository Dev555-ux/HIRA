"""Tests for GET /health/whatsapp (Sprint 69, DEPLOY-5) — the webhook
liveness signal an external uptime monitor polls, separate from the plain
/health liveness check Railway itself uses."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Message


def _client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_inbound_message(db_session, *, created_at: datetime) -> None:
    business = Business(name="Test Business")
    db_session.add(business)
    db_session.flush()
    customer = Customer(business_id=business.id, wa_phone="+15551230000")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=business.id, customer_id=customer.id, status="active")
    db_session.add(conversation)
    db_session.flush()
    db_session.add(
        Message(
            conversation_id=conversation.id,
            business_id=business.id,
            direction="inbound",
            body="Hi",
            status="received",
            created_at=created_at,
        )
    )
    db_session.commit()


def test_no_traffic_yet_returns_200(db_session):
    client = _client(db_session)
    resp = client.get("/health/whatsapp")
    assert resp.status_code == 200
    assert resp.json() == {"status": "no_traffic_yet"}
    app.dependency_overrides.clear()


def test_recent_inbound_traffic_is_healthy(db_session):
    _make_inbound_message(db_session, created_at=_now() - timedelta(minutes=5))
    client = _client(db_session)
    resp = client.get("/health/whatsapp")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    app.dependency_overrides.clear()


def test_stale_inbound_traffic_returns_503(db_session, monkeypatch):
    monkeypatch.setattr(settings, "webhook_stale_threshold_minutes", 60)
    _make_inbound_message(db_session, created_at=_now() - timedelta(minutes=90))
    client = _client(db_session)
    resp = client.get("/health/whatsapp")
    assert resp.status_code == 503
    assert resp.json()["status"] == "stale"
    app.dependency_overrides.clear()


def test_stale_traffic_raises_a_sentry_alert(db_session, monkeypatch):
    captured = []
    monkeypatch.setattr("app.main.capture_message", captured.append)
    monkeypatch.setattr(settings, "webhook_stale_threshold_minutes", 60)
    _make_inbound_message(db_session, created_at=_now() - timedelta(minutes=90))
    client = _client(db_session)

    client.get("/health/whatsapp")

    assert len(captured) == 1
    assert "silent" in captured[0]
    app.dependency_overrides.clear()


def test_healthy_traffic_does_not_raise_an_alert(db_session, monkeypatch):
    captured = []
    monkeypatch.setattr("app.main.capture_message", captured.append)
    _make_inbound_message(db_session, created_at=_now() - timedelta(minutes=5))
    client = _client(db_session)

    client.get("/health/whatsapp")

    assert captured == []
    app.dependency_overrides.clear()
