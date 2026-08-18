"""Sprint 65 PR 5 — proof that outbound Instagram messages flow through the
*exact same* production pipeline WhatsApp uses: MessagingService ->
ChannelManager -> InstagramProvider.send() -> Meta, with no Instagram-only
special case. Mirrors tests/test_outbound_cutover.py's shape (the real
default `sender`, not a test-injected fake, stubbed only at the
`httpx.Client.post` transport layer) plus Autonomous Mode (`send_reply`)
and a retry-path proof `test_outbound_cutover.py` doesn't cover.
"""

from __future__ import annotations

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

import app.channels.instagram  # noqa: F401 — registers InstagramProvider regardless
import app.channels.whatsapp  # noqa: F401 — of test collection order; see

# app/channels/__init__.py::register_all()'s docstring for why this can't be
# assumed to happen as a side effect of some other test file's own imports.
from app.core.config import settings
from app.instagram.credentials import store_credentials
from app.models import Business, Conversation, Customer, Message
from app.services.messaging_service import MessagingService

IGSID = "IGSID_998877"


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _business_with_conversation(
    db, *, message_status: str, message_type: str = "text", media: list[dict] | None = None
):
    business = Business(name="Studio A")
    db.add(business)
    db.flush()
    store_credentials(
        db,
        business.id,
        page_id="PAGE_1",
        page_access_token="page-token",
        instagram_business_account_id="IG_ACCT_1",
        instagram_username="studio_a",
    )
    customer = Customer(business_id=business.id, wa_phone=IGSID)
    db.add(customer)
    db.flush()
    conversation = Conversation(
        business_id=business.id, customer_id=customer.id, status="active", channel="instagram"
    )
    db.add(conversation)
    db.flush()
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body="We're open until 6pm today.",
        type=message_type,
        media=media,
        status=message_status,
    )
    db.add(message)
    db.commit()
    return business, conversation, customer, message


# --- manual reply / approval flow --------------------------------------


def test_approve_and_send_routes_instagram_through_channel_manager_end_to_end(
    db_session, monkeypatch
):
    captured_requests: list[dict] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        captured_requests.append({"url": url, "headers": headers, "json": json})
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.approved-1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval"
    )

    result = MessagingService(db_session).approve_and_send(
        business.id, message.id
    )  # no sender override — the real production path

    assert result.status == "sent"
    assert result.wa_message_id == "mid.approved-1"
    assert len(captured_requests) == 1
    assert captured_requests[0]["url"].endswith("/PAGE_1/messages")
    assert captured_requests[0]["headers"]["Authorization"] == "Bearer page-token"
    assert captured_requests[0]["json"] == {
        "recipient": {"id": IGSID},
        "message": {"text": "We're open until 6pm today."},
        "messaging_type": "RESPONSE",
    }

    persisted = db_session.scalars(select(Message).where(Message.id == message.id)).one()
    assert persisted.status == "sent"
    assert persisted.wa_message_id == "mid.approved-1"


def test_approve_and_send_surfaces_a_non_retryable_instagram_failure(db_session, monkeypatch):
    def fake_post_error(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(400, json={"error": {"message": "invalid token", "code": 190}})

    monkeypatch.setattr(httpx.Client, "post", fake_post_error)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval"
    )

    with pytest.raises(Exception):
        MessagingService(db_session).approve_and_send(business.id, message.id)

    persisted = db_session.scalars(select(Message).where(Message.id == message.id)).one()
    assert persisted.status == "failed"
    assert persisted.ai_meta["failure_reason"] == "channel_send_failed"


def test_approve_and_send_returns_409_style_error_when_instagram_not_connected(db_session):
    """No InstagramCredential stored at all — same "not connected" path
    WhatsApp gets when it has no stored credential, now reachable for a
    second channel."""
    from app.services.messaging import WhatsAppNotConnectedError

    business = Business(name="Studio B")
    db_session.add(business)
    db_session.flush()
    customer = Customer(business_id=business.id, wa_phone="IGSID_no_creds")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(
        business_id=business.id, customer_id=customer.id, status="active", channel="instagram"
    )
    db_session.add(conversation)
    db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body="hi",
        type="text",
        status="pending_approval",
    )
    db_session.add(message)
    db_session.commit()

    with pytest.raises(WhatsAppNotConnectedError, match="Instagram"):
        MessagingService(db_session).approve_and_send(business.id, message.id)


# --- autonomous mode ------------------------------------------------------


def test_send_reply_routes_instagram_through_channel_manager_end_to_end(db_session, monkeypatch):
    captured_requests: list[dict] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        captured_requests.append(json)
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.auto-1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, conversation, _customer, message = _business_with_conversation(
        db_session, message_status="sending"
    )

    MessagingService(db_session).send_reply(business, conversation, message)  # no sender override

    assert message.status == "sent"
    assert message.wa_message_id == "mid.auto-1"
    assert len(captured_requests) == 1
    assert captured_requests[0]["recipient"] == {"id": IGSID}


def test_send_reply_marks_failed_when_instagram_not_connected(db_session):
    business = Business(name="Studio C")
    db_session.add(business)
    db_session.flush()
    customer = Customer(business_id=business.id, wa_phone="IGSID_no_creds")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(
        business_id=business.id, customer_id=customer.id, status="active", channel="instagram"
    )
    db_session.add(conversation)
    db_session.flush()
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body="hi",
        type="text",
        status="sending",
    )
    db_session.add(message)
    db_session.commit()

    MessagingService(db_session).send_reply(business, conversation, message)

    assert message.status == "failed"
    assert message.ai_meta["failure_reason"] == "channel_not_connected"


# --- delivery receipt / retry -----------------------------------------


def test_delivery_receipt_external_message_id_is_persisted(db_session, monkeypatch):
    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.receipt-1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval"
    )

    MessagingService(db_session).approve_and_send(business.id, message.id)

    persisted = db_session.scalars(select(Message).where(Message.id == message.id)).one()
    assert persisted.wa_message_id == "mid.receipt-1"


def test_retryable_failure_is_retried_by_channel_manager_then_succeeds(db_session, monkeypatch):
    """Proves ChannelManager's existing retry loop (unmodified by this PR)
    works for Instagram exactly as it does for WhatsApp: a 5xx response is
    retried, and a later success within the attempt budget still lands."""
    attempts: list[int] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        attempts.append(1)
        if len(attempts) < 2:
            return httpx.Response(500, text="temporary failure")
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.retried-1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    monkeypatch.setattr("app.services.channel_manager.RETRY_BACKOFF_SECONDS", 0.0)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval"
    )

    result = MessagingService(db_session).approve_and_send(business.id, message.id)

    assert result.status == "sent"
    assert result.wa_message_id == "mid.retried-1"
    assert len(attempts) == 2  # one failed attempt, one retry that succeeded


def test_non_retryable_failure_is_not_retried_by_channel_manager(db_session, monkeypatch):
    attempts: list[int] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        attempts.append(1)
        return httpx.Response(400, json={"error": {"message": "bad request", "code": 100}})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval"
    )

    with pytest.raises(Exception):
        MessagingService(db_session).approve_and_send(business.id, message.id)

    assert len(attempts) == 1  # non-retryable — exactly one attempt, no retry loop


# --- media (Sprint 65 PR 6) ----------------------------------------------

_IMAGE_MEDIA = [
    {"kind": "image", "url": "https://cdn.example/photo.jpg", "mime_type": None, "caption": None}
]


def test_approve_and_send_routes_manual_media_reply_through_channel_manager(db_session, monkeypatch):
    """Proves a human-approved draft carrying media (e.g. attached via
    PATCH /messages/{id}/draft) flows Message.media -> MessagingService ->
    ChannelManager -> InstagramProvider.send() -> Meta's attachment
    endpoint, with the message's text dropped (Meta's own constraint)."""
    captured_requests: list[dict] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        captured_requests.append(json)
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.media-approved"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval", message_type="image", media=_IMAGE_MEDIA
    )

    result = MessagingService(db_session).approve_and_send(business.id, message.id)

    assert result.status == "sent"
    assert len(captured_requests) == 1
    assert captured_requests[0]["message"] == {
        "attachment": {"type": "image", "payload": {"url": "https://cdn.example/photo.jpg"}}
    }


def test_send_reply_routes_autonomous_media_reply_through_channel_manager(db_session, monkeypatch):
    """Same pipeline proof for Autonomous Mode (send_reply) — the
    transport layer carries a Message's media identically regardless of
    which mode produced it; this PR does not give the AI a new tool to
    choose media, only proves the pipe carries it when a Message row has
    some (see PR notes)."""
    captured_requests: list[dict] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        captured_requests.append(json)
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.media-auto"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, conversation, _customer, message = _business_with_conversation(
        db_session, message_status="sending", message_type="image", media=_IMAGE_MEDIA
    )

    MessagingService(db_session).send_reply(business, conversation, message)

    assert message.status == "sent"
    assert len(captured_requests) == 1
    assert captured_requests[0]["message"]["attachment"]["type"] == "image"


def test_approve_and_send_text_only_message_unaffected_by_media_plumbing(db_session, monkeypatch):
    """Regression guard: a plain-text draft (media=None) still sends
    exactly the old {"text": ...} payload — the media plumbing must be
    fully additive."""
    captured_requests: list[dict] = []

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        captured_requests.append(json)
        return httpx.Response(200, json={"recipient_id": IGSID, "message_id": "mid.text-1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    business, _conversation, _customer, message = _business_with_conversation(
        db_session, message_status="pending_approval"
    )

    MessagingService(db_session).approve_and_send(business.id, message.id)

    assert captured_requests[0]["message"] == {"text": "We're open until 6pm today."}
