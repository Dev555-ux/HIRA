"""Tests for the WhatsApp webhook: verification, signature, persistence, dedupe, dispatch."""

import hashlib
import hmac
import json

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Message
from app.webhooks.whatsapp import _get_or_create_customer, get_reply_dispatcher
from app.whatsapp.credentials import store_credentials

TEST_APP_SECRET = "test-app-secret"


@pytest.fixture(autouse=True)
def _whatsapp_encryption_key(monkeypatch):
    # Sprint 69: signature verification now decrypts each business's own
    # stored app secret rather than reading one global settings value.
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _client(db_session):
    """Returns (client, dispatched). The reply dispatcher is overridden to record
    calls instead of scheduling real background generation."""
    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, message_id, user_text):
            dispatched.append((conversation_id, message_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    return TestClient(app), dispatched


def _connected_business(db, phone_number_id="PN1", app_secret=TEST_APP_SECRET) -> Business:
    """Creates and commits a business with a stored, encrypted WhatsApp
    credential — the precondition (Sprint 69) for the webhook to accept
    anything signed with `app_secret` for this phone_number_id."""
    business = Business(name="Clinic A", whatsapp_phone_number_id=phone_number_id)
    db.add(business)
    db.flush()
    store_credentials(db, business.id, access_token="test-token", app_secret=app_secret)
    db.commit()
    return business


def _sign(body: bytes, app_secret: str = TEST_APP_SECRET) -> str:
    digest = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _inbound_payload(phone_number_id: str, wa_message_id: str, from_phone="+15551230000"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"wa_id": from_phone, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "id": wa_message_id,
                                    "from": from_phone,
                                    "type": "text",
                                    "text": {"body": "Hi, are you open today?"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def test_verification_handshake_ok(db_session):
    client, _ = _client(db_session)
    resp = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.whatsapp_verify_token,
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "12345"
    app.dependency_overrides.clear()


def test_verification_handshake_wrong_token(db_session):
    client, _ = _client(db_session)
    resp = client.get(
        "/webhooks/whatsapp",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"},
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_post_rejects_bad_signature(db_session):
    _connected_business(db_session)  # a real, connected business — signature is still wrong
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.1")).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_post_rejects_unknown_phone_number_id(db_session):
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("no-such-number", "wamid.1")).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        # Correctly signed, but for a phone_number_id no business has connected.
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_post_rejects_a_business_with_no_stored_credential(db_session):
    # Business.whatsapp_phone_number_id set directly (bypassing the connect
    # flow, as old data/a partial migration might look) but no
    # WhatsAppCredential row — must be rejected, not fall back to anything.
    business = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db_session.add(business)
    db_session.commit()
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.1")).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_post_rejects_a_signature_signed_with_a_different_businesss_secret(db_session):
    # Two connected businesses, each with their own secret (Sprint 69's core
    # guarantee) — a payload claiming to be business A's phone number but
    # signed with business B's secret must be rejected.
    _connected_business(db_session, phone_number_id="PN1", app_secret="secret-a")
    _connected_business(db_session, phone_number_id="PN2", app_secret="secret-b")
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.1")).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body, "secret-b"),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_post_accepts_each_business_signed_with_its_own_secret(db_session):
    # The positive case for the above: two businesses, each correctly signed
    # with their own secret, both succeed independently.
    _connected_business(db_session, phone_number_id="PN1", app_secret="secret-a")
    _connected_business(db_session, phone_number_id="PN2", app_secret="secret-b")
    client, dispatched = _client(db_session)

    body_a = json.dumps(_inbound_payload("PN1", "wamid.a")).encode()
    resp_a = client.post(
        "/webhooks/whatsapp",
        content=body_a,
        headers={
            "X-Hub-Signature-256": _sign(body_a, "secret-a"),
            "Content-Type": "application/json",
        },
    )
    body_b = json.dumps(_inbound_payload("PN2", "wamid.b")).encode()
    resp_b = client.post(
        "/webhooks/whatsapp",
        content=body_b,
        headers={
            "X-Hub-Signature-256": _sign(body_b, "secret-b"),
            "Content-Type": "application/json",
        },
    )

    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert len(dispatched) == 2
    app.dependency_overrides.clear()


def test_post_persists_inbound_and_dispatches_reply(db_session):
    _connected_business(db_session)

    client, dispatched = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.abc")).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
    assert len(inbound) == 1
    assert inbound[0].body == "Hi, are you open today?"
    assert db_session.scalars(select(Customer)).first().wa_phone == "+15551230000"
    assert db_session.scalars(select(Conversation)).first().status == "active"
    assert len(dispatched) == 1  # reply generation was scheduled
    # Sprint 76: dispatch is handed the *actual* persisted inbound Message's
    # id (not just conversation_id/text) — record_execution_trace's
    # trigger_message_id depends on this being the real row, not a
    # placeholder, all the way from app/webhooks/whatsapp.py.
    assert dispatched[0][1] == inbound[0].id
    app.dependency_overrides.clear()


def test_post_ignores_status_callback(db_session):
    _connected_business(db_session)

    client, dispatched = _client(db_session)
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PN1"},
                            "statuses": [{"id": "wamid.x", "status": "delivered"}],
                        }
                    }
                ]
            }
        ]
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert db_session.scalars(select(Message)).all() == []  # nothing stored
    assert len(dispatched) == 0  # no reply generation dispatched
    app.dependency_overrides.clear()


def test_post_dedupes_repeated_message_id(db_session):
    _connected_business(db_session)

    client, dispatched = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.dup")).encode()
    headers = {"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"}

    client.post("/webhooks/whatsapp", content=body, headers=headers)
    client.post("/webhooks/whatsapp", content=body, headers=headers)  # same id again

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
    assert len(inbound) == 1  # not double-stored
    assert len(dispatched) == 1  # dispatched only for the first (new) message
    app.dependency_overrides.clear()


def test_get_or_create_customer_recovers_from_concurrent_insert_race(db_session, monkeypatch):
    """Two overlapping webhook deliveries for the same phone number can both
    pass the existence check before either flushes. Simulates that by
    forcing this call's own check to report "not found" for exactly one
    call, even though a customer for this (business, phone) already exists
    (committed by the "other" delivery) — uq_customer_business_phone must
    still be what stops the duplicate INSERT, recovered via SAVEPOINT
    rollback + re-query rather than raising an unhandled IntegrityError."""
    business = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db_session.add(business)
    db_session.commit()

    winner = Customer(business_id=business.id, wa_phone="+15551230000", display_name="Winner")
    db_session.add(winner)
    db_session.commit()

    real_scalars = db_session.scalars
    calls = {"n": 0}

    class _EmptyResult:
        def first(self):
            return None

    def fake_scalars(stmt, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _EmptyResult()
        return real_scalars(stmt, *args, **kwargs)

    monkeypatch.setattr(db_session, "scalars", fake_scalars)

    customer = _get_or_create_customer(db_session, business.id, "+15551230000", "Loser's name")

    assert customer.id == winner.id
    all_customers = db_session.scalars(
        select(Customer).where(
            Customer.business_id == business.id, Customer.wa_phone == "+15551230000"
        )
    ).all()
    assert len(all_customers) == 1
