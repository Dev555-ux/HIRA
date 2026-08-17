"""Sprint 64A PR 5 — inbound cutover integration tests.

Production's `_persist_inbound` (app/webhooks/whatsapp.py) now delegates
message-content extraction to `app.channels.whatsapp.parsing.parse_messages`
instead of its own inline copy — these tests exercise that through the real
webhook route end to end, against a real Postgres, reusing the same
fixtures as tests/test_whatsapp_webhook.py. Everything already covered
there (signature verification, dedup, status-callback skipping, the
concurrent-insert race) is unchanged and re-verified simply by that file
continuing to pass unmodified — this file adds only what's genuinely new
for the cutover: proof of the actual wiring, plus the two integration
cases (unsupported message type, malformed payload) that weren't
explicitly covered before.

tests/webhooks/test_whatsapp_outbox.py's AI-enqueue-payload assertions
(conversation_id/message_id/user_text) are the "AI enqueue parity" check
for this PR — reused unmodified rather than duplicated here, since they
already exercise the exact same `_persist_inbound` this PR changed.
"""

import hashlib
import hmac
import json

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

import app.channels.whatsapp.parsing as parsing_module
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, Customer, Message
from app.webhooks.whatsapp import get_reply_dispatcher
from app.whatsapp.credentials import store_credentials

TEST_APP_SECRET = "test-app-secret"


@pytest.fixture(autouse=True)
def _whatsapp_encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _client(db_session):
    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, message_id, user_text):
            dispatched.append((conversation_id, message_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    return TestClient(app), dispatched


def _connected_business(db, phone_number_id="PN1", app_secret=TEST_APP_SECRET) -> Business:
    business = Business(name="Clinic A", whatsapp_phone_number_id=phone_number_id)
    db.add(business)
    db.flush()
    store_credentials(db, business.id, access_token="test-token", app_secret=app_secret)
    db.commit()
    return business


def _sign(body: bytes, app_secret: str = TEST_APP_SECRET) -> str:
    return f"sha256={hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()}"


def _payload(message: dict, phone_number_id="PN1", from_phone="+15551230000"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [
                                {"wa_id": from_phone, "profile": {"name": "Ada Lovelace"}}
                            ],
                            "messages": [message],
                        }
                    }
                ]
            }
        ]
    }


def test_persist_inbound_routes_through_the_shared_parser(db_session, monkeypatch):
    """Proves the wiring, not just a behavioral coincidence: `_persist_inbound`
    genuinely calls `parse_messages` for its message-content extraction."""
    calls: list[tuple[list[dict], list[dict]]] = []
    real_parse_messages = parsing_module.parse_messages

    def spy(messages, contacts):
        calls.append((messages, contacts))
        return real_parse_messages(messages, contacts)

    monkeypatch.setattr("app.webhooks.whatsapp.parse_messages", spy)
    _connected_business(db_session)
    client, dispatched = _client(db_session)

    message = {
        "id": "wamid.cutover-1",
        "from": "+15551230000",
        "type": "text",
        "text": {"body": "Are you open today?"},
    }
    body = json.dumps(_payload(message)).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    assert len(calls) == 1
    called_messages, called_contacts = calls[0]
    assert called_messages == [message]
    assert called_contacts == [{"wa_id": "+15551230000", "profile": {"name": "Ada Lovelace"}}]

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).one()
    assert inbound.body == "Are you open today?"
    assert len(dispatched) == 1
    app.dependency_overrides.clear()


def test_sender_display_name_persists_end_to_end(db_session):
    _connected_business(db_session)
    client, _ = _client(db_session)

    message = {
        "id": "wamid.name-1",
        "from": "+15551230000",
        "type": "text",
        "text": {"body": "hi"},
    }
    body = json.dumps(_payload(message)).encode()
    client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    customer = db_session.scalars(select(Customer)).one()
    assert customer.wa_phone == "+15551230000"
    assert customer.display_name == "Ada Lovelace"
    app.dependency_overrides.clear()


def test_unsupported_message_type_persists_with_empty_body(db_session):
    """Matches pre-cutover behavior exactly: only delivery/status callbacks
    are skipped. A message of a type HIRA doesn't extract text for (image,
    audio, interactive, ...) still persists a Message row with an empty
    body — it is not silently dropped."""
    _connected_business(db_session)
    client, dispatched = _client(db_session)

    message = {
        "id": "wamid.image-1",
        "from": "+15551230000",
        "type": "image",
        "image": {"id": "m1"},
    }
    body = json.dumps(_payload(message)).encode()
    resp = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )

    assert resp.status_code == 200
    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).one()
    assert inbound.body == ""
    assert inbound.type == "image"
    assert inbound.wa_message_id == "wamid.image-1"
    assert len(dispatched) == 1  # still dispatched, same as a text message
    app.dependency_overrides.clear()


def test_malformed_json_body_is_rejected_and_nothing_is_persisted(db_session):
    _connected_business(db_session)
    client, dispatched = _client(db_session)

    resp = client.post(
        "/webhooks/whatsapp",
        content=b"not valid json {{{",
        headers={"X-Hub-Signature-256": "sha256=irrelevant", "Content-Type": "application/json"},
    )

    assert resp.status_code == 403
    assert db_session.scalars(select(Message)).all() == []
    assert dispatched == []
    app.dependency_overrides.clear()


def test_empty_json_object_body_is_rejected(db_session):
    """Valid JSON, but with no `phone_number_id` anywhere to route on."""
    client, dispatched = _client(db_session)

    resp = client.post(
        "/webhooks/whatsapp",
        content=b"{}",
        headers={"X-Hub-Signature-256": "sha256=irrelevant", "Content-Type": "application/json"},
    )

    assert resp.status_code == 403
    assert db_session.scalars(select(Message)).all() == []
    assert dispatched == []
    app.dependency_overrides.clear()
