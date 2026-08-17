"""Sprint 64A PR 7 — MessagingService, the single messaging orchestration
layer.

DB-backed (MessagingService is the one layer in this pipeline that touches
Postgres, by design — see its module docstring). Focused, direct
unit-level tests of `record_inbound()` and `_send()` live here; the much
larger surface of `send_reply()`/`approve_and_send()` (tool execution,
status transitions, compensation on commit failure) is already covered
exhaustively by tests/test_orchestrator.py (Autonomous Mode) and
tests/test_replies.py (Assisted Mode) — both now call MessagingService
directly and continue to pass unmodified in substance (only the call
syntax changed, from a free function to a method), which is itself the
proof this PR's relocation didn't change behavior.
"""

from __future__ import annotations


import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.channels.base.message import NormalizedMessage
from app.core.config import settings
from app.jobs.models import JobOutbox
from app.models import Business, Conversation, Customer, Message
from app.services.messaging import WhatsAppSendError
from app.services.messaging_service import MessagingService


@pytest.fixture(autouse=True)
def _whatsapp_encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _business(db) -> Business:
    business = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db.add(business)
    db.commit()
    return business


def _normalized(
    wa_message_id="wamid.1", from_phone="+15551230000", text="hi", display_name="Test User"
):
    return NormalizedMessage(
        channel="whatsapp",
        external_conversation_id=from_phone,
        external_message_id=wa_message_id,
        external_sender_id=from_phone,
        sender_display_name=display_name,
        text=text,
        raw={"id": wa_message_id, "from": from_phone, "type": "text", "text": {"body": text}},
    )


# --- record_inbound: persistence -------------------------------------------


def test_record_inbound_persists_customer_conversation_and_message(db_session):
    business = _business(db_session)

    result = MessagingService(db_session).record_inbound(business.id, [_normalized()])

    assert len(result) == 1
    conversation_id, message_id, wa_message_id, text = result[0]
    assert wa_message_id == "wamid.1"
    assert text == "hi"

    customer = db_session.scalars(select(Customer).where(Customer.business_id == business.id)).one()
    assert customer.wa_phone == "+15551230000"
    assert customer.display_name == "Test User"

    conversation = db_session.get(Conversation, conversation_id)
    assert conversation.customer_id == customer.id
    assert conversation.status == "active"
    assert conversation.window_expires_at is not None

    message = db_session.get(Message, message_id)
    assert message.body == "hi"
    assert message.direction == "inbound"
    assert message.wa_message_id == "wamid.1"


def test_record_inbound_reuses_existing_customer_and_conversation(db_session):
    business = _business(db_session)
    service = MessagingService(db_session)
    service.record_inbound(business.id, [_normalized(wa_message_id="wamid.1")])
    service.record_inbound(business.id, [_normalized(wa_message_id="wamid.2")])

    customers = db_session.scalars(
        select(Customer).where(Customer.business_id == business.id)
    ).all()
    conversations = db_session.scalars(
        select(Conversation).where(Conversation.business_id == business.id)
    ).all()
    assert len(customers) == 1
    assert len(conversations) == 1


# --- record_inbound: deduplication ------------------------------------


def test_record_inbound_dedupes_by_external_message_id(db_session):
    business = _business(db_session)
    service = MessagingService(db_session)

    first = service.record_inbound(business.id, [_normalized(wa_message_id="wamid.dup")])
    second = service.record_inbound(business.id, [_normalized(wa_message_id="wamid.dup")])

    assert len(first) == 1
    assert len(second) == 0  # deduped — no new row, nothing returned
    inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
    assert len(inbound) == 1


def test_record_inbound_handles_a_mixed_batch_of_new_and_duplicate_messages(db_session):
    business = _business(db_session)
    service = MessagingService(db_session)
    service.record_inbound(business.id, [_normalized(wa_message_id="wamid.existing")])

    result = service.record_inbound(
        business.id,
        [
            _normalized(wa_message_id="wamid.existing"),  # duplicate
            _normalized(wa_message_id="wamid.new"),  # new
        ],
    )

    assert len(result) == 1
    assert result[0][2] == "wamid.new"


# --- record_inbound: enqueue -------------------------------------------


def test_record_inbound_enqueues_ai_job_when_outbox_enabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "use_transactional_outbox", True)
    business = _business(db_session)

    result = MessagingService(db_session).record_inbound(business.id, [_normalized()])
    conversation_id, message_id, _wa_message_id, text = result[0]

    job = db_session.scalars(select(JobOutbox)).one()
    assert job.task_name == "generate_ai_reply"
    assert job.business_id == business.id
    assert job.payload["conversation_id"] == str(conversation_id)
    assert job.payload["message_id"] == str(message_id)
    assert job.payload["user_text"] == text
    assert job.idempotency_key == "whatsapp:wamid.1"


def test_record_inbound_enqueues_nothing_when_outbox_disabled(db_session, monkeypatch):
    monkeypatch.setattr(settings, "use_transactional_outbox", False)
    business = _business(db_session)

    MessagingService(db_session).record_inbound(business.id, [_normalized()])

    assert db_session.scalars(select(JobOutbox)).all() == []


# --- get-or-create customer: concurrency ------------------------------


def test_get_or_create_customer_recovers_from_concurrent_insert_race(db_session, monkeypatch):
    """Two overlapping webhook deliveries for the same phone number can both
    pass the existence check before either flushes. Simulates that by
    forcing this call's own check to report "not found" for exactly one
    call, even though a customer for this (business, phone) already exists
    (committed by the "other" delivery) — uq_customer_business_phone must
    still be what stops the duplicate INSERT, recovered via SAVEPOINT
    rollback + re-query rather than raising an unhandled IntegrityError.
    Moved from tests/test_whatsapp_webhook.py (Sprint 64A PR 7) — same
    test, same target logic, now a MessagingService method instead of a
    module-level webhook function."""
    business = _business(db_session)

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

    service = MessagingService(db_session)
    customer = service._get_or_create_customer(business.id, "+15551230000", "Loser's name")

    assert customer.id == winner.id
    all_customers = db_session.scalars(
        select(Customer).where(
            Customer.business_id == business.id, Customer.wa_phone == "+15551230000"
        )
    ).all()
    assert len(all_customers) == 1


# --- _send: the default outbound transport ------------------------------


def test_send_success_returns_the_provider_message_id(db_session, monkeypatch):
    import httpx

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(200, json={"messages": [{"id": "wamid.sent-1"}]})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    result = MessagingService(db_session)._send(
        "PN1", "+15551230000", "hi", access_token="test-token"
    )

    assert result == "wamid.sent-1"


def test_send_failure_raises_whatsapp_send_error(db_session, monkeypatch):
    import httpx

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(401, text="unauthorized")

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    with pytest.raises(WhatsAppSendError):
        MessagingService(db_session)._send("PN1", "+15551230000", "hi", access_token="bad-token")
