"""Sprint 64A PR 6 — proof that the *real* default `sender` (no test-injected
fake) still works end to end through Approve & Send.

Every existing test in tests/test_replies.py and tests/test_dashboard_api.py
injects its own fake `sender`, by design (so they don't hit real HTTP) — none
of them actually exercise `send_via_channel_manager`, the new default. This
file is the one place that does, using the same `httpx.Client.post`-level
stub tests/test_ai_reply_worker_idempotency.py already uses to prove the
Autonomous Mode default path (see that file's `_stub_whatsapp_transport`
docstring for why the patch has to be at the transport layer, not a named
function — a default parameter value is bound at import time).
"""

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.models import Business, Conversation, Customer, Message
from app.services.messaging_service import MessagingService
from app.whatsapp.credentials import store_credentials


@pytest.fixture(autouse=True)
def _whatsapp_encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _pending_reply(db) -> tuple[Business, Message]:
    business = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db.add(business)
    db.flush()
    store_credentials(db, business.id, access_token="test-token", app_secret="test-secret")
    customer = Customer(business_id=business.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=business.id, customer_id=customer.id, status="active")
    db.add(conversation)
    db.flush()
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body="We're open until 6pm today.",
        type="text",
        status="pending_approval",
    )
    db.add(message)
    db.commit()
    return business, message


def test_approve_and_send_default_sender_routes_through_channel_manager_end_to_end(
    db_session, monkeypatch
):
    captured_requests: list[dict] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        captured_requests.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(200, json={"messages": [{"id": "wamid.approved-1"}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, message = _pending_reply(db_session)

    result = MessagingService(db_session).approve_and_send(
        business.id, message.id
    )  # no sender override

    assert result.status == "sent"
    assert result.wa_message_id == "wamid.approved-1"
    assert len(captured_requests) == 1
    assert captured_requests[0]["json"]["to"] == "+15551230000"
    assert captured_requests[0]["json"]["text"]["body"] == "We're open until 6pm today."

    persisted = db_session.scalars(select(Message).where(Message.id == message.id)).one()
    assert persisted.status == "sent"
    assert persisted.wa_message_id == "wamid.approved-1"


def test_approve_and_send_default_sender_surfaces_send_failure_end_to_end(db_session, monkeypatch):
    def fake_post_error(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(401, text="unauthorized")

    monkeypatch.setattr(httpx.Client, "post", fake_post_error)

    business, message = _pending_reply(db_session)

    with pytest.raises(Exception):  # approve_and_send re-raises whatever sender raised
        MessagingService(db_session).approve_and_send(business.id, message.id)

    persisted = db_session.scalars(select(Message).where(Message.id == message.id)).one()
    assert persisted.status == "failed"
    assert persisted.ai_meta["failure_reason"] == "channel_send_failed"
