"""Tests for the orchestrator and background reply processing (mock providers)."""

from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.ai import processing
from app.ai.lead_tools import CREATE_LEAD
from app.ai.llm.base import LLMProvider, LLMResponse, ToolCall
from app.ai.llm.mock import MockProvider
from app.ai.orchestrator import generate_reply
from app.ai.tools import BOOK_APPOINTMENT, CHECK_AVAILABILITY, preview_tool_call
from app.calendar.providers.base import CalendarNotConnectedError
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.models import Appointment, Business, Conversation, Escalation, Message
from tests.conftest import TEST_DATABASE_URL
from tests.test_knowledge_base import FakeEmbeddingProvider
from app.ai.knowledge_base import index_entry


def _setup_business_with_kb(db):
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    index_entry(
        db,
        biz.id,
        "Hours",
        "We are open 9am to 5pm on weekdays.",
        provider=FakeEmbeddingProvider(),
    )
    conversation = Conversation(business_id=biz.id, customer_id=_make_customer(db, biz.id))
    db.add(conversation)
    db.flush()
    return biz, conversation


def _make_customer(db, business_id):
    from app.models import Customer

    customer = Customer(business_id=business_id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    return customer.id


def test_generate_reply_injects_knowledge_and_returns_response(db_session):
    _, conversation = _setup_business_with_kb(db_session)

    response, retrieved = generate_reply(
        db_session,
        conversation,
        "what are your opening hours?",
        llm=MockProvider(fixed_reply="We're open 9am-5pm on weekdays."),
        embedding=FakeEmbeddingProvider(),
    )

    assert response.text == "We're open 9am-5pm on weekdays."
    assert len(retrieved) >= 1
    assert any("9am" in e.content for e in retrieved)


class _SequencedProvider(LLMProvider):
    """Returns a different canned response on each successive call — lets a
    test exercise generate_reply's one-extra-call check_availability round
    trip (MockProvider only ever returns one fixed response per test)."""

    def __init__(self, responses):
        self._responses = list(responses)

    def generate(self, *, system, messages, max_tokens=None, tools=None):
        return self._responses.pop(0)


def test_generate_reply_passes_write_tool_calls_through_unexecuted(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    provider = MockProvider(fixed_reply="", fixed_tool_calls=[tool_call])

    response, _ = generate_reply(
        db_session,
        conversation,
        "book me tuesday at 2pm",
        llm=provider,
        embedding=FakeEmbeddingProvider(),
    )

    assert response.tool_calls == [tool_call]


def test_generate_reply_executes_check_availability_then_asks_again(db_session, monkeypatch):
    _, conversation = _setup_business_with_kb(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )
    availability_call = ToolCall(
        id="1",
        name=CHECK_AVAILABILITY,
        arguments={
            "starts_at": "2026-08-05T09:00:00+00:00",
            "ends_at": "2026-08-05T17:00:00+00:00",
        },
    )
    provider = _SequencedProvider(
        [
            LLMResponse(text="", model="mock-1", tool_calls=[availability_call]),
            LLMResponse(text="We have a slot at 9am, does that work?", model="mock-1"),
        ]
    )

    response, _ = generate_reply(
        db_session,
        conversation,
        "can I book tuesday morning?",
        llm=provider,
        embedding=FakeEmbeddingProvider(),
    )

    assert response.text == "We have a slot at 9am, does that work?"
    assert response.tool_calls is None


def test_generate_and_store_reply_persists_pending_outbound(db_session, monkeypatch):
    _, conversation = _setup_business_with_kb(db_session)
    db_session.commit()  # make visible to the processing session

    # Point the background processor at the test database, and use the mock LLM.
    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="Yes, we're open today!"),
    )

    processing.generate_and_store_reply(conversation.id, "are you open today?")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].status == "pending_approval"
    assert outbound[0].body == "Yes, we're open today!"
    assert outbound[0].ai_meta["model"] == "mock-1"


# --- AI-3: non-text inbound messages get an honest reply, not silence -----


def test_non_text_message_gets_canned_reply_without_calling_the_llm(db_session, monkeypatch):
    _, conversation = _setup_business_with_kb(db_session)
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)

    def _fail_if_called(name=None):
        raise AssertionError("the LLM must not be called for a non-text message")

    monkeypatch.setattr("app.ai.orchestrator.get_llm_provider", _fail_if_called)

    # app/webhooks/whatsapp.py::_extract_text collapses a non-text inbound
    # message (image/audio/video/...) to "" before dispatch.
    processing.generate_and_store_reply(conversation.id, "")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].status == "pending_approval"
    assert outbound[0].type == "text"
    assert "only read text" in outbound[0].body
    assert outbound[0].ai_meta["model"] == "none"


# --- REL-2: an AI generation failure leaves a trace, not silence -----------


def test_generation_failure_escalates_instead_of_leaving_silence(db_session, monkeypatch):
    _, conversation = _setup_business_with_kb(db_session)
    conversation_id = conversation.id
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)

    def _boom(db, conversation, user_text, *, llm=None, embedding=None):
        raise RuntimeError("simulated LLM provider outage")

    monkeypatch.setattr(processing, "generate_reply", _boom)

    processing.generate_and_store_reply(conversation_id, "are you open today?")

    outbound = db_session.scalars(
        select(Message).where(
            Message.conversation_id == conversation_id, Message.direction == "outbound"
        )
    ).all()
    assert len(outbound) == 1
    assert outbound[0].status == "escalated"
    assert "flagged for you to follow up" in outbound[0].body

    conversation = db_session.get(Conversation, conversation_id)
    assert conversation.status == "escalated"

    escalations = db_session.scalars(
        select(Escalation).where(Escalation.conversation_id == conversation_id)
    ).all()
    assert len(escalations) == 1
    assert escalations[0].reason == "external_failure"
    assert escalations[0].status == "open"


def test_assisted_mode_stores_proposed_tool_call_without_executing(db_session, monkeypatch):
    from app.models import Customer

    biz = Business(name="Clinic A")  # assisted (default)
    db_session.add(biz)
    db_session.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )
    executed = {"called": False}
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: executed.update(called=True),
    )

    processing.generate_and_store_reply(conversation.id, "book me tuesday at 2pm")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].type == "tool_call"
    assert outbound[0].status == "pending_approval"
    assert "Cleaning" in outbound[0].body
    assert outbound[0].ai_meta["tool_name"] == BOOK_APPOINTMENT
    assert executed["called"] is False  # nothing touched the calendar
    # Section A1: Assisted Mode's stored body is exactly preview_tool_call()'s
    # output — unchanged, still the text the Pending queue shows for editing.
    assert outbound[0].body == preview_tool_call(tool_call)


def test_assisted_mode_stores_proposed_lead_tool_call_without_executing(db_session, monkeypatch):
    """DEC-033: CRM tool calls go through the same generic pending-approval
    path as calendar ones — no separate wiring in processing.py needed."""
    from app.models import Customer

    biz = Business(name="Clinic A")  # assisted (default)
    db_session.add(biz)
    db_session.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )

    processing.generate_and_store_reply(conversation.id, "I'd like a quote please")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].type == "tool_call"
    assert outbound[0].status == "pending_approval"
    assert outbound[0].ai_meta["tool_name"] == CREATE_LEAD
    from app.models import Lead

    assert db_session.scalars(select(Lead)).first() is None  # nothing written yet


def test_autonomous_mode_executes_lead_tool_call_immediately(db_session, monkeypatch):
    from app.models import Customer, Lead

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )
    sent: dict = {}

    def fake_sender(phone_number_id, to, body):
        sent.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.sent1"

    processing.generate_and_store_reply(
        conversation.id, "I'd like a quote please", sender=fake_sender
    )

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].type == "tool_call"
    assert outbound[0].status == "sent"
    assert outbound[0].ai_meta["tool_result"] == "Lead logged."
    assert sent["body"] == outbound[0].body
    assert db_session.scalars(select(Lead)).first() is not None
    # Section A1: the internal, dashboard-only preview text must never be
    # what's actually sent to the customer over WhatsApp.
    assert sent["body"] != preview_tool_call(tool_call)
    assert sent["body"] == "Thanks — that's been taken care of."


def test_autonomous_mode_sends_reply_immediately(db_session, monkeypatch):
    from app.models import Customer

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    index_entry(db_session, biz.id, "Hours", "Open 9-5 weekdays.", provider=FakeEmbeddingProvider())
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9am-5pm."),
    )
    sent: dict = {}

    def fake_sender(phone_number_id, to, body):
        sent.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.sent1"

    processing.generate_and_store_reply(conversation.id, "are you open?", sender=fake_sender)

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].status == "sent"  # auto-sent, no approval needed
    assert outbound[0].wa_message_id == "wamid.sent1"
    assert sent == {
        "phone_number_id": "PN1",
        "to": "+15550001111",
        "body": "We are open 9am-5pm.",
    }


def test_autonomous_mode_executes_tool_call_immediately(db_session, monkeypatch):
    from app.models import Customer

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )
    sent: dict = {}

    def fake_sender(phone_number_id, to, body):
        sent.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.sent1"

    processing.generate_and_store_reply(
        conversation.id, "book me tuesday at 2pm", sender=fake_sender
    )

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].type == "tool_call"
    assert outbound[0].status == "sent"  # executed + sent immediately, no approval gate
    assert outbound[0].ai_meta["tool_result"] == "Appointment booked."
    assert sent["body"] == outbound[0].body
    from app.models import Appointment

    assert db_session.scalars(select(Appointment)).first() is not None
    # Section A1: the internal, dashboard-only preview text ("Book: Cleaning
    # (...)") must never be what's actually sent to the customer.
    assert sent["body"] != preview_tool_call(tool_call)
    assert sent["body"] == (
        "You're all set! Cleaning is booked for 2026-08-05T14:00:00 to 2026-08-05T15:00:00."
    )


def test_autonomous_mode_marks_failed_when_tool_call_execution_fails(db_session, monkeypatch):
    from app.models import Customer

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )

    def _raise_not_connected(db, business_id):
        raise CalendarNotConnectedError("not connected")

    monkeypatch.setattr("app.ai.tools.get_appointment_service", _raise_not_connected)
    sender_called = {"called": False}

    def fake_sender(phone_number_id, to, body):
        sender_called["called"] = True
        return "wamid.sent1"

    processing.generate_and_store_reply(
        conversation.id, "book me tuesday at 2pm", sender=fake_sender
    )

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].status == "failed"
    assert sender_called["called"] is False  # never attempted to send a confirmation


# --- Section A4: tool effect + Message update must commit atomically --------


def test_autonomous_mode_final_commit_failure_leaves_no_stale_message_or_appointment(
    db_session, monkeypatch
):
    """If the single commit in generate_and_store_reply fails after the tool
    ran (with commit=False) and the WhatsApp send fired, nothing should be
    left half-done: no Message row at all (not even a stale
    "pending_approval" one a human could re-approve), no Appointment row
    (its flush rolled back with everything else), and the now-orphaned
    external calendar event cleaned up. A retry that then succeeds must
    create exactly one appointment, proving the failed attempt left no
    duplicate-booking residue behind."""
    from app.models import Customer

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()
    conversation_id = conversation.id

    real_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    commit_calls = {"n": 0}

    def flaky_session_factory():
        session = real_sessionmaker()
        original_commit = session.commit

        def flaky_commit():
            commit_calls["n"] += 1
            if commit_calls["n"] == 1:
                raise SQLAlchemyError("simulated failure on the single outer commit")
            return original_commit()

        session.commit = flaky_commit
        return session

    monkeypatch.setattr(processing, "SessionLocal", flaky_session_factory)

    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )
    provider = MockCalendarProvider()
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(db, business_id, provider, calendar_id="primary"),
    )
    sent = {"count": 0}

    def fake_sender(phone_number_id, to, body):
        sent["count"] += 1
        return f"wamid.out{sent['count']}"

    processing.generate_and_store_reply(
        conversation_id, "book me tuesday at 2pm", sender=fake_sender
    )

    # Nothing durably persisted -- no stale pending Message, no orphaned Appointment.
    assert (
        db_session.scalars(
            select(Message).where(Message.conversation_id == conversation_id)
        ).all()
        == []
    )
    assert db_session.scalars(select(Appointment)).all() == []

    # The WhatsApp send fired for real before the commit failed.
    assert sent["count"] == 1

    # The external calendar event was cleaned up, not left dangling.
    assert all(e.status == "cancelled" for e in provider._events.values())

    # A retry (this time succeeding) creates exactly one appointment.
    monkeypatch.setattr(processing, "SessionLocal", real_sessionmaker)
    processing.generate_and_store_reply(
        conversation_id, "book me tuesday at 2pm", sender=fake_sender
    )

    appointments = db_session.scalars(select(Appointment)).all()
    assert len(appointments) == 1
