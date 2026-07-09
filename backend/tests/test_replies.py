"""Tests for the pending-reply actions (approve, edit, reject, regenerate, escalate)."""

import uuid

import pytest

from app.ai.llm.mock import MockProvider
from app.models import Business, Conversation, Customer, Escalation, Message
from app.services.messaging import WhatsAppSendError
from app.services.replies import (
    approve_and_send,
    escalate_reply,
    regenerate_draft,
    reject_reply,
    update_draft,
)
from tests.test_knowledge_base import FakeEmbeddingProvider


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


# --- update_draft (Phase 1: editable drafts) ---------------------------------


def test_update_draft_edits_body(db_session):
    biz, _, msg = _pending_reply(db_session)

    result = update_draft(db_session, biz.id, msg.id, body="Actually, we're open 24/7.")

    assert result.body == "Actually, we're open 24/7."
    assert result.status == "pending_approval"
    db_session.refresh(msg)
    assert msg.body == "Actually, we're open 24/7."


def test_update_draft_rejects_already_approved_message(db_session):
    biz, _, msg = _pending_reply(db_session)
    msg.status = "sent"
    db_session.flush()

    with pytest.raises(ValueError):
        update_draft(db_session, biz.id, msg.id, body="edited")


def test_update_draft_is_tenant_scoped(db_session):
    biz, _, msg = _pending_reply(db_session)
    other_business_id = uuid.uuid4()

    with pytest.raises(ValueError):
        update_draft(db_session, other_business_id, msg.id, body="edited")


# --- reject_reply (Phase 2) ---------------------------------------------------


def test_reject_reply_marks_rejected(db_session):
    biz, _, msg = _pending_reply(db_session)

    result = reject_reply(db_session, biz.id, msg.id)

    assert result.status == "rejected"
    db_session.refresh(msg)
    assert msg.status == "rejected"


def test_reject_reply_rejects_non_pending_message(db_session):
    biz, _, msg = _pending_reply(db_session)
    msg.status = "sent"
    db_session.flush()

    with pytest.raises(ValueError):
        reject_reply(db_session, biz.id, msg.id)


def test_reject_reply_is_tenant_scoped(db_session):
    biz, _, msg = _pending_reply(db_session)
    other_business_id = uuid.uuid4()

    with pytest.raises(ValueError):
        reject_reply(db_session, other_business_id, msg.id)


# --- regenerate_draft (Phase 3) ----------------------------------------------


def _pending_reply_with_history(db):
    """A pending reply preceded by the customer message that triggered it."""
    biz, customer, msg = _pending_reply(db)
    inbound = Message(
        conversation_id=msg.conversation_id,
        business_id=biz.id,
        direction="inbound",
        body="are you open on weekends?",
        type="text",
        status="received",
    )
    db.add(inbound)
    db.flush()
    return biz, customer, msg


def test_regenerate_draft_replaces_body_and_marks_regenerated(db_session):
    biz, _, msg = _pending_reply_with_history(db_session)

    result = regenerate_draft(
        db_session,
        biz.id,
        msg.id,
        llm=MockProvider(fixed_reply="Yes, we're open weekends 10-2."),
        embedding=FakeEmbeddingProvider(),
    )

    assert result.body == "Yes, we're open weekends 10-2."
    assert result.status == "pending_approval"
    assert result.ai_meta["regenerated"] is True


def test_regenerate_draft_keeps_conversation_history(db_session):
    biz, _, msg = _pending_reply_with_history(db_session)
    conversation_id = msg.conversation_id

    regenerate_draft(
        db_session,
        biz.id,
        msg.id,
        llm=MockProvider(fixed_reply="new draft"),
        embedding=FakeEmbeddingProvider(),
    )

    remaining = db_session.query(Message).filter(Message.conversation_id == conversation_id).count()
    assert remaining == 2  # the original inbound message + the (same, updated) draft


def test_regenerate_draft_rejects_non_pending_message(db_session):
    biz, _, msg = _pending_reply_with_history(db_session)
    msg.status = "sent"
    db_session.flush()

    with pytest.raises(ValueError):
        regenerate_draft(db_session, biz.id, msg.id)


def test_regenerate_draft_is_tenant_scoped(db_session):
    biz, _, msg = _pending_reply_with_history(db_session)
    other_business_id = uuid.uuid4()

    with pytest.raises(ValueError):
        regenerate_draft(db_session, other_business_id, msg.id)


def test_regenerate_draft_fails_without_a_customer_message(db_session):
    biz, _, msg = _pending_reply(db_session)  # no inbound message in this conversation

    with pytest.raises(ValueError):
        regenerate_draft(
            db_session, biz.id, msg.id, llm=MockProvider(), embedding=FakeEmbeddingProvider()
        )


# --- escalate_reply (Phase 4) --------------------------------------------------


def test_escalate_reply_creates_escalation_and_marks_conversation(db_session):
    biz, _, msg = _pending_reply(db_session)
    conversation_id = msg.conversation_id

    message, escalation = escalate_reply(db_session, biz.id, msg.id)

    assert message.status == "escalated"
    conversation = db_session.get(Conversation, conversation_id)
    assert conversation.status == "escalated"
    assert escalation.business_id == biz.id
    assert escalation.conversation_id == conversation_id
    assert escalation.status == "open"
    stored = db_session.get(Escalation, escalation.id)
    assert stored is not None


def test_escalate_reply_keeps_conversation_history(db_session):
    biz, _, msg = _pending_reply_with_history(db_session)
    conversation_id = msg.conversation_id

    escalate_reply(db_session, biz.id, msg.id)

    remaining = db_session.query(Message).filter(Message.conversation_id == conversation_id).count()
    assert remaining == 2  # both messages still exist, untouched


def test_escalate_reply_rejects_non_pending_message(db_session):
    biz, _, msg = _pending_reply(db_session)
    msg.status = "sent"
    db_session.flush()

    with pytest.raises(ValueError):
        escalate_reply(db_session, biz.id, msg.id)


def test_escalate_reply_is_tenant_scoped(db_session):
    biz, _, msg = _pending_reply(db_session)
    other_business_id = uuid.uuid4()

    with pytest.raises(ValueError):
        escalate_reply(db_session, other_business_id, msg.id)
