"""Tests for the pending-reply actions (approve, edit, reject, regenerate, escalate)."""

import threading
import uuid

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.ai.lead_tools import CREATE_LEAD
from app.ai.llm.base import ToolCall
from app.ai.llm.mock import MockProvider
from app.ai.tool_results import ToolExecutionResult
from app.ai.tools import BOOK_APPOINTMENT
from app.calendar.providers.base import CalendarError
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.models import Appointment, Business, Conversation, Customer, Escalation, Message
from app.services.messaging import WhatsAppNotConnectedError, WhatsAppSendError
from app.services.replies import (
    approve_and_send,
    escalate_reply,
    regenerate_draft,
    reject_reply,
    update_draft,
)
from tests.conftest import TEST_DATABASE_URL
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


def test_approve_and_send_rejects_when_whatsapp_not_connected(db_session):
    biz, _, msg = _pending_reply(db_session, business_phone=None)
    sent = []

    def sender_that_should_never_run(*_args):
        sent.append(_args)
        return "wamid.should-not-happen"

    with pytest.raises(WhatsAppNotConnectedError):
        approve_and_send(db_session, biz.id, msg.id, sender=sender_that_should_never_run)

    db_session.refresh(msg)
    assert msg.status == "pending_approval"  # untouched — no partial side effect
    assert sent == []  # the Meta API was never called


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


def test_regenerate_draft_can_flip_a_text_draft_into_a_tool_call(db_session):
    biz, _, msg = _pending_reply_with_history(db_session)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )

    result = regenerate_draft(
        db_session,
        biz.id,
        msg.id,
        llm=MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
        embedding=FakeEmbeddingProvider(),
    )

    assert result.type == "tool_call"
    assert "Cleaning" in result.body
    assert result.ai_meta["tool_name"] == BOOK_APPOINTMENT
    assert result.ai_meta["tool_arguments"] == tool_call.arguments


def test_regenerate_draft_can_flip_a_tool_call_draft_back_to_text(db_session):
    biz, customer, msg = _pending_reply_with_history(db_session)
    msg.type = "tool_call"
    msg.ai_meta = {"tool_name": BOOK_APPOINTMENT, "tool_arguments": {"starts_at": "x"}}
    db_session.flush()

    result = regenerate_draft(
        db_session,
        biz.id,
        msg.id,
        llm=MockProvider(fixed_reply="Sorry, that time isn't available."),
        embedding=FakeEmbeddingProvider(),
    )

    assert result.type == "text"
    assert result.body == "Sorry, that time isn't available."
    assert "tool_name" not in result.ai_meta


# --- approve_and_send with a proposed tool call (Sprint 29, DEC-032) ---------


def _pending_tool_call_reply(db, *, business_phone="PN1"):
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
        body="Book: Cleaning (2026-08-05T14:00:00 – 2026-08-05T15:00:00)",
        type="tool_call",
        status="pending_approval",
        ai_meta={
            "tool_name": BOOK_APPOINTMENT,
            "tool_arguments": {
                "starts_at": "2026-08-05T14:00:00",
                "ends_at": "2026-08-05T15:00:00",
                "summary": "Cleaning",
            },
        },
    )
    db.add(msg)
    db.flush()
    return biz, customer, msg


def _pending_lead_tool_call_reply(db, *, business_phone="PN1"):
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
        body="Log as a new lead (source: WhatsApp inquiry)",
        type="tool_call",
        status="pending_approval",
        ai_meta={"tool_name": CREATE_LEAD, "tool_arguments": {"source": "WhatsApp inquiry"}},
    )
    db.add(msg)
    db.flush()
    return biz, customer, msg


def test_approve_tool_call_executes_then_sends(db_session, monkeypatch):
    biz, customer, msg = _pending_tool_call_reply(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )
    captured = {}

    def fake_sender(phone_number_id, to, body):
        captured.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.out1"

    result = approve_and_send(db_session, biz.id, msg.id, sender=fake_sender)

    assert result.status == "sent"
    assert result.ai_meta["tool_result"] == "Appointment booked."
    assert captured["body"] == msg.body
    from app.models import Appointment

    assert db_session.query(Appointment).count() == 1


def test_approve_tool_call_marks_failed_when_execution_fails(db_session, monkeypatch):
    biz, _, msg = _pending_tool_call_reply(db_session)

    def _fails(db, business_id, tool_call, *, customer_id, conversation_id, commit=True):
        from app.ai.tools import ToolExecutionResult

        return ToolExecutionResult(False, "slot no longer available")

    monkeypatch.setattr("app.services.replies.execute_tool_call", _fails)
    sender_called = {"called": False}

    def fake_sender(*args):
        sender_called["called"] = True
        return "wamid.out1"

    with pytest.raises(CalendarError):
        approve_and_send(db_session, biz.id, msg.id, sender=fake_sender)

    db_session.refresh(msg)
    assert msg.status == "failed"
    assert sender_called["called"] is False  # never attempted to send


def test_approve_lead_tool_call_executes_then_sends(db_session):
    """DEC-033: approve_and_send dispatches a CRM tool call through the exact
    same code path as a calendar one — no branch added for CRM specifically."""
    biz, customer, msg = _pending_lead_tool_call_reply(db_session)
    captured = {}

    def fake_sender(phone_number_id, to, body):
        captured.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.out1"

    result = approve_and_send(db_session, biz.id, msg.id, sender=fake_sender)

    assert result.status == "sent"
    assert result.ai_meta["tool_result"] == "Lead logged."
    assert captured["body"] == msg.body
    from app.models import Lead

    assert db_session.query(Lead).count() == 1


# --- concurrent approval (Section A3 — TOCTOU race on approve_and_send) -------


def test_concurrent_approve_only_one_wins_and_sends_once(db_session):
    """Two requests approving the same pending reply race between the load
    and the commit. Only one may claim the row, execute any side effect, and
    send; the other must lose before sending anything."""
    biz, customer, msg = _pending_reply(db_session)
    db_session.commit()
    message_id, business_id = msg.id, biz.id

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    send_calls: list[tuple] = []
    send_lock = threading.Lock()

    def fake_sender(phone_number_id, to, body):
        with send_lock:
            send_calls.append((phone_number_id, to, body))
        return f"wamid.out{len(send_calls)}"

    results: dict[str, str] = {}
    errors: dict[str, Exception] = {}
    start_barrier = threading.Barrier(2)

    def worker(name):
        session = test_sessionmaker()
        start_barrier.wait(timeout=5)
        try:
            result = approve_and_send(session, business_id, message_id, sender=fake_sender)
            results[name] = result.status
        except ValueError as exc:
            errors[name] = exc
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(name,)) for name in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(send_calls) == 1  # WhatsApp send fired exactly once
    assert list(results.values()) == ["sent"]  # exactly one winner
    assert len(errors) == 1  # exactly one loser
    assert all(isinstance(e, ValueError) for e in errors.values())

    db_session.expire_all()
    final = db_session.get(Message, message_id)
    assert final.status == "sent"
    assert final.wa_message_id == "wamid.out1"


def test_concurrent_approve_tool_call_executes_tool_exactly_once(db_session, monkeypatch):
    """Same race, but on a message.type == 'tool_call' reply: the calendar
    tool itself must run exactly once too, not just the WhatsApp send."""
    biz, customer, msg = _pending_tool_call_reply(db_session)
    db_session.commit()
    message_id, business_id = msg.id, biz.id

    call_count = {"n": 0}
    call_lock = threading.Lock()

    def fake_execute_tool_call(
        db, business_id, tool_call, *, customer_id, conversation_id, commit=True
    ):
        with call_lock:
            call_count["n"] += 1
        return ToolExecutionResult(True, "Appointment booked.", uuid.uuid4())

    monkeypatch.setattr("app.services.replies.execute_tool_call", fake_execute_tool_call)

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    send_calls: list[str] = []
    send_lock = threading.Lock()

    def fake_sender(phone_number_id, to, body):
        with send_lock:
            send_calls.append(body)
        return "wamid.out1"

    results: dict[str, str] = {}
    errors: dict[str, Exception] = {}
    start_barrier = threading.Barrier(2)

    def worker(name):
        session = test_sessionmaker()
        start_barrier.wait(timeout=5)
        try:
            result = approve_and_send(session, business_id, message_id, sender=fake_sender)
            results[name] = result.status
        except ValueError as exc:
            errors[name] = exc
        finally:
            session.close()

    threads = [threading.Thread(target=worker, args=(name,)) for name in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert call_count["n"] == 1  # tool executed exactly once
    assert len(send_calls) == 1  # WhatsApp send fired exactly once
    assert list(results.values()) == ["sent"]
    assert len(errors) == 1
    assert all(isinstance(e, ValueError) for e in errors.values())

    db_session.expire_all()
    final = db_session.get(Message, message_id)
    assert final.status == "sent"


# --- Section A4: tool effect + Message update must commit atomically --------


def test_assisted_mode_final_commit_failure_leaves_no_orphaned_appointment(db_session, monkeypatch):
    """If the final commit in approve_and_send fails after the tool ran
    (with commit=False) and the WhatsApp send fired, the Appointment's flush
    must roll back with it -- not persist independently and orphan a real
    calendar booking. The now-orphaned external event must be cleaned up,
    and the Message must land on "sending" (the last durably committed
    state), not "pending_approval" -- so it can't be silently re-approved
    and double-booked. A deliberate recovery retry that then succeeds must
    create exactly one appointment, proving the failure left no
    duplicate-booking residue."""
    biz, customer, msg = _pending_tool_call_reply(db_session)
    message_id, business_id = msg.id, biz.id

    provider = MockCalendarProvider()
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, provider, calendar_id="primary"
        ),
    )

    original_commit = db_session.commit
    commit_calls = {"n": 0}

    def flaky_commit():
        commit_calls["n"] += 1
        if commit_calls["n"] == 2:  # 1 = the A3 claim commit, 2 = the final commit
            raise SQLAlchemyError("simulated failure on the final Message commit")
        return original_commit()

    monkeypatch.setattr(db_session, "commit", flaky_commit)

    sent = {"count": 0}

    def fake_sender(phone_number_id, to, body):
        sent["count"] += 1
        return f"wamid.out{sent['count']}"

    with pytest.raises(SQLAlchemyError):
        approve_and_send(db_session, business_id, message_id, sender=fake_sender)

    monkeypatch.setattr(db_session, "commit", original_commit)
    # The mocked commit raised without going through real SQLAlchemy commit
    # machinery, so the transaction is still open on this connection; a real
    # failed commit aborts the transaction as part of handling the error,
    # and the request's session then gets closed by get_db's teardown --
    # simulate that same "nothing left dangling on this connection" reset.
    db_session.rollback()

    # No orphaned appointment -- the tool's flushed insert rolled back
    # together with the failed Message commit.
    assert db_session.scalars(select(Appointment)).all() == []

    # The WhatsApp send fired for real before the commit failed.
    assert sent["count"] == 1

    # The external calendar event was cleaned up, not left dangling.
    assert all(e.status == "cancelled" for e in provider._events.values())

    # Stuck at the last durably committed state ("sending"), not
    # "pending_approval" -- so a normal approval request can't silently
    # re-execute the tool and double-book.
    db_session.expire_all()
    stuck = db_session.get(Message, message_id)
    assert stuck.status == "sending"

    # A deliberate recovery retry (e.g. support resetting the message back
    # to pending_approval) executes the tool exactly once more.
    stuck.status = "pending_approval"
    db_session.commit()
    approve_and_send(db_session, business_id, message_id, sender=fake_sender)

    appointments = db_session.scalars(select(Appointment)).all()
    assert len(appointments) == 1


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
