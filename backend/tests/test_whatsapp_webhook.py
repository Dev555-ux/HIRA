"""Tests for the WhatsApp webhook: verification, signature, persistence, dedupe, dispatch."""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Message
from app.webhooks.whatsapp import get_reply_dispatcher


def _client(db_session):
    """Returns (client, dispatched). The reply dispatcher is overridden to record
    calls instead of scheduling real background generation."""
    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, user_text):
            dispatched.append((conversation_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    return TestClient(app), dispatched


def _sign(body: bytes) -> str:
    digest = hmac.new(settings.whatsapp_app_secret.encode(), body, hashlib.sha256).hexdigest()
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
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.1")).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": "sha256=deadbeef", "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_post_persists_inbound_and_dispatches_reply(db_session):
    business = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db_session.add(business)
    db_session.commit()

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
    app.dependency_overrides.clear()


def test_post_dedupes_repeated_message_id(db_session):
    business = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db_session.add(business)
    db_session.commit()

    client, dispatched = _client(db_session)
    body = json.dumps(_inbound_payload("PN1", "wamid.dup")).encode()
    headers = {"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"}

    client.post("/webhooks/whatsapp", content=body, headers=headers)
    client.post("/webhooks/whatsapp", content=body, headers=headers)  # same id again

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
    assert len(inbound) == 1  # not double-stored
    assert len(dispatched) == 1  # dispatched only for the first (new) message
    app.dependency_overrides.clear()
