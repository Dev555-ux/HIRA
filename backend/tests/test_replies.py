"""Tests for approve_and_send (closing the Assisted-Mode loop)."""

import uuid

import pytest

from app.models import Business, Conversation, Customer, Message
from app.services.messaging import WhatsAppSendError
from app.services.replies import approve_and_send


def _pending_reply(db, *, business_phone="PN1"):
    biz = Business(name="Clinic A", whatsapp_phone_number_id=business_phone)
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    conv = Conversation(business_id=biz.id, customer_id=customer.id)
    db.add(conv)
    db.flush()
    msg = Message(
        conversation_id=conv.id,
        business_id=biz.id,
        direction="outbound",
        body="Yes, we're open 9-5 on weekdays.",
        type="text",
        status="pending_approval",
    )
    db.add(msg)
    db.flush()
    return biz, customer, msg


def test_approve_and_send_marks_sent(db_session):
    biz, customer, msg = _pending_reply(db_session)
    captured = {}

    def fake_sender(phone_number_id, to, body):
        captured.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.out123"

    result = approve_and_send(db_session, biz.id, msg.id, sender=fake_sender)

    assert result.status == "sent"
    assert result.wa_message_id == "wamid.out123"
    assert captured == {
        "phone_number_id": "PN1",
        "to": "+15551230000",
        "body": "Yes, we're open 9-5 on weekdays.",
    }


def test_approve_and_send_marks_failed_on_send_error(db_session):
    biz, _, msg = _pending_reply(db_session)

    def failing_sender(*_args):
        raise WhatsAppSendError("boom")

    with pytest.raises(WhatsAppSendError):
        approve_and_send(db_session, biz.id, msg.id, sender=failing_sender)

    db_session.refresh(msg)
    assert msg.status == "failed"


def test_approve_and_send_rejects_non_pending_message(db_session):
    biz, _, msg = _pending_reply(db_session)
    msg.status = "sent"
    db_session.flush()

    with pytest.raises(ValueError):
        approve_and_send(db_session, biz.id, msg.id, sender=lambda *a: "x")


def test_approve_and_send_is_tenant_scoped(db_session):
    biz, _, msg = _pending_reply(db_session)
    other_business_id = uuid.uuid4()

    with pytest.raises(ValueError):
        approve_and_send(db_session, other_business_id, msg.id, sender=lambda *a: "x")
