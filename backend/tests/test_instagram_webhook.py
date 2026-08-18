"""Tests for the Instagram webhook: verification, signature, business
resolution, persistence, dedupe, and AI enqueue (Sprint 65 PR 3).

Mirrors tests/test_whatsapp_webhook.py's shape. The one structural
difference: Instagram connects every business through one HIRA-owned Meta
App (Sprint 65 PR 2), so signature verification uses one shared
INSTAGRAM_APP_SECRET, not a per-business stored secret — there is no
per-business-signing-secret test here the way WhatsApp's suite has one,
because that isn't how this channel's OAuth was built.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_db
from app.instagram.credentials import store_credentials
from app.jobs.models import JobOutbox
from app.main import app
from app.models import Business, Conversation, Customer, Message
from app.webhooks.whatsapp import get_reply_dispatcher

TEST_APP_SECRET = "test-instagram-app-secret"


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "instagram_app_secret", TEST_APP_SECRET)


def _client(db_session):
    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, message_id, user_text):
            dispatched.append((conversation_id, message_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    return TestClient(app), dispatched


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _connected_business(db, ig_account_id="IG_ACCT_1") -> Business:
    business = Business(name="Clinic A")
    db.add(business)
    db.flush()
    store_credentials(
        db,
        business.id,
        page_id="page-1",
        page_access_token="page-token",
        instagram_business_account_id=ig_account_id,
        instagram_username="clinic_a",
    )
    db.commit()
    return business


def _sign(body: bytes, secret: str = TEST_APP_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _inbound_payload(
    ig_account_id: str, message_id: str, sender_id="IGSID_123", text="Are you open today?"
):
    return {
        "object": "instagram",
        "entry": [
            {
                "id": ig_account_id,
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": sender_id},
                        "recipient": {"id": ig_account_id},
                        "timestamp": 1700000000,
                        "message": {"mid": message_id, "text": text},
                    }
                ],
            }
        ],
    }


# --- GET verification handshake ---------------------------------------------


def test_verification_handshake_ok(db_session):
    client, _ = _client(db_session)
    resp = client.get(
        "/webhooks/instagram",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": settings.instagram_verify_token,
            "hub.challenge": "12345",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "12345"


def test_verification_handshake_wrong_token(db_session):
    client, _ = _client(db_session)
    resp = client.get(
        "/webhooks/instagram",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "x"},
    )
    assert resp.status_code == 403


# --- signature verification --------------------------------------------------


def test_post_rejects_missing_signature(db_session):
    _connected_business(db_session)
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram", content=body, headers={"Content-Type": "application/json"}
    )
    assert resp.status_code == 403


def test_post_rejects_malformed_signature(db_session):
    _connected_business(db_session)
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={
            "X-Hub-Signature-256": "not-a-valid-signature",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 403


def test_post_rejects_invalid_signature(db_session):
    _connected_business(db_session)
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body, "wrong-secret"),
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 403
    assert db_session.scalars(select(Message)).all() == []


def test_post_rejects_when_app_secret_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "instagram_app_secret", "")
    _connected_business(db_session)
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 403


def test_post_rejects_invalid_signature_logs_without_leaking_body(db_session, caplog):
    """Sprint 65 PR 7: a signature failure must produce a structured log
    line, and it must never include the raw request body or signature
    header (which could echo customer message content)."""
    _connected_business(db_session)
    client, _ = _client(db_session)
    body = json.dumps(
        _inbound_payload("IG_ACCT_1", "mid.1", text="a secret customer message")
    ).encode()
    bad_sig = _sign(body, "wrong-secret")

    with caplog.at_level("WARNING", logger="app.webhooks.instagram"):
        resp = client.post(
            "/webhooks/instagram",
            content=body,
            headers={"X-Hub-Signature-256": bad_sig, "Content-Type": "application/json"},
        )

    assert resp.status_code == 403
    messages = [r.message for r in caplog.records]
    assert any("signature" in m.lower() for m in messages)
    assert not any("a secret customer message" in m for m in messages)
    assert not any(bad_sig in m for m in messages)


def test_post_accepts_a_correctly_signed_payload(db_session):
    _connected_business(db_session)
    client, dispatched = _client(db_session)
    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert len(dispatched) == 1


# --- business resolution ------------------------------------------------------


def test_post_rejects_unknown_ig_account_id(db_session):
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("no-such-account", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        # Correctly signed (shared app secret), but no business has
        # connected this Instagram account.
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 403
    assert db_session.scalars(select(Message)).all() == []


def test_post_rejects_unknown_ig_account_id_logs_the_account(db_session, caplog):
    client, _ = _client(db_session)
    body = json.dumps(_inbound_payload("no-such-account", "mid.1")).encode()

    with caplog.at_level("WARNING", logger="app.webhooks.instagram"):
        resp = client.post(
            "/webhooks/instagram",
            content=body,
            headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
        )

    assert resp.status_code == 403
    messages = [r.message for r in caplog.records]
    assert any("no-such-account" in m for m in messages)


def test_post_routes_to_the_correct_business_when_several_are_connected(db_session):
    biz_a = _connected_business(db_session, ig_account_id="IG_ACCT_A")
    biz_b = _connected_business(db_session, ig_account_id="IG_ACCT_B")
    client, _ = _client(db_session)

    body = json.dumps(_inbound_payload("IG_ACCT_B", "mid.1")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    message = db_session.scalars(select(Message).where(Message.direction == "inbound")).one()
    assert message.business_id == biz_b.id
    assert message.business_id != biz_a.id


# --- persistence / dedupe / AI enqueue ---------------------------------------


def test_post_persists_inbound_and_dispatches_reply(db_session):
    _connected_business(db_session)
    client, dispatched = _client(db_session)

    body = json.dumps(
        _inbound_payload(
            "IG_ACCT_1", "mid.abc", sender_id="IGSID_7", text="Hi, are you open today?"
        )
    ).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
    assert len(inbound) == 1
    assert inbound[0].body == "Hi, are you open today?"
    assert db_session.scalars(select(Customer)).first().wa_phone == "IGSID_7"
    assert db_session.scalars(select(Conversation)).first().status == "active"
    assert len(dispatched) == 1
    assert dispatched[0][1] == inbound[0].id


def test_post_persists_inbound_media(db_session):
    """Sprint 65 PR 6: an inbound image attachment persists onto
    Message.media and Message.type derives from the attachment kind, not
    the WhatsApp-only `raw.get("type")` fallback (Instagram's raw event
    dict has no top-level "type" key)."""
    _connected_business(db_session)
    client, _dispatched = _client(db_session)

    payload = _inbound_payload("IG_ACCT_1", "mid.img-1", sender_id="IGSID_9", text="")
    payload["entry"][0]["messaging"][0]["message"] = {
        "mid": "mid.img-1",
        "attachments": [{"type": "image", "payload": {"url": "https://cdn.example/photo.jpg"}}],
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).one()
    assert inbound.type == "image"
    assert inbound.body == ""
    assert inbound.media == [
        {
            "kind": "image",
            "url": "https://cdn.example/photo.jpg",
            "mime_type": None,
            "caption": None,
        }
    ]


def test_post_dedupes_repeated_message_id(db_session):
    _connected_business(db_session)
    client, dispatched = _client(db_session)
    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.dup")).encode()
    headers = {"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"}

    client.post("/webhooks/instagram", content=body, headers=headers)
    client.post("/webhooks/instagram", content=body, headers=headers)

    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
    assert len(inbound) == 1
    assert len(dispatched) == 1


def test_post_ignores_non_message_events(db_session):
    """A read-receipt event (no `message` key) — must be recognized and
    skipped, never crash the route, never persist anything."""
    _connected_business(db_session)
    client, dispatched = _client(db_session)
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG_ACCT_1",
                "messaging": [
                    {
                        "sender": {"id": "IGSID_1"},
                        "recipient": {"id": "IG_ACCT_1"},
                        "read": {"mid": "mid.1"},
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert db_session.scalars(select(Message)).all() == []
    assert len(dispatched) == 0


def test_post_rejects_malformed_json_body(db_session):
    _connected_business(db_session)
    client, _ = _client(db_session)
    body = b"not json"
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 403


def test_post_enqueues_ai_job_when_outbox_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "use_transactional_outbox", True)
    business = _connected_business(db_session)
    client, dispatched = _client(db_session)

    body = json.dumps(_inbound_payload("IG_ACCT_1", "mid.job")).encode()
    resp = client.post(
        "/webhooks/instagram",
        content=body,
        headers={"X-Hub-Signature-256": _sign(body), "Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    job = db_session.scalars(select(JobOutbox).where(JobOutbox.business_id == business.id)).one()
    assert job.task_name == "generate_ai_reply"
    # Legacy in-process dispatch must not also fire once the outbox owns it.
    assert len(dispatched) == 0
