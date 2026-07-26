"""Tests for the orchestrator and background reply processing (mock providers)."""

from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from app.ai import processing
from app.ai.lead_tools import CREATE_LEAD, SET_LEAD_FOLLOW_UP, UPDATE_LEAD_STAGE
from app.ai.llm.base import LLMProvider, LLMResponse, ToolCall
from app.ai.llm.mock import MockProvider
from app.ai.orchestrator import generate_reply
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    RESCHEDULE_APPOINTMENT,
    preview_tool_call,
)
from app.calendar.providers.base import CalendarNotConnectedError
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.core.config import settings
from app.models import Appointment, Business, Conversation, Escalation, Message
from app.whatsapp.credentials import store_credentials
from tests.conftest import TEST_DATABASE_URL
from tests.test_knowledge_base import FakeEmbeddingProvider
from app.ai.knowledge_base import index_entry


def _connect_whatsapp(db, monkeypatch, business_id):
    """Autonomous-mode sends (Sprint 69) require a stored, encrypted
    WhatsAppCredential in addition to Business.whatsapp_phone_number_id —
    call this after creating an autonomous-mode test business that's
    expected to actually reach the send step."""
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    store_credentials(db, business_id, access_token="test-token", app_secret="test-secret")


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


def _setup_business_without_kb(db):
    """Sprint 55: the counterpart to _setup_business_with_kb — a brand-new
    business that hasn't uploaded any Business Knowledge yet, which is
    exactly the state Demo Mode exists for."""
    biz = Business(name="Clinic B")
    db.add(biz)
    db.flush()
    conversation = Conversation(business_id=biz.id, customer_id=_make_customer(db, biz.id))
    db.add(conversation)
    db.flush()
    return biz, conversation


class _SpyProvider(LLMProvider):
    """Records the `tools` argument of every call, so a test can assert
    Demo Mode never offers the model calendar/CRM tools (Sprint 55) — there's
    nothing real yet for it to check availability or create leads against."""

    def __init__(self, fixed_reply="Hello! I'm HIRA."):
        self._fixed_reply = fixed_reply
        self.calls: list[dict] = []

    def generate(self, *, system, messages, max_tokens=None, tools=None):
        self.calls.append({"system": system, "messages": messages, "tools": tools})
        return LLMResponse(text=self._fixed_reply, model="mock-1")


def test_generate_reply_injects_knowledge_and_returns_response(db_session):
    _, conversation = _setup_business_with_kb(db_session)

    response, retrieved, plan = generate_reply(
        db_session,
        conversation,
        "what are your opening hours?",
        llm=MockProvider(fixed_reply="We're open 9am-5pm on weekdays."),
        embedding=FakeEmbeddingProvider(),
    )

    assert response.text == "We're open 9am-5pm on weekdays."
    assert len(retrieved) >= 1
    assert any("9am" in e.content for e in retrieved)


def test_generate_reply_uses_demo_prompt_and_no_tools_without_business_knowledge(db_session):
    # Sprint 55: the actual feature — a business with zero Business
    # Knowledge gets the Demo Mode prompt and no tool schemas at all, so
    # there's nothing left for the model to misfire toward (e.g. proposing
    # check_availability on a bare "Hi" — the exact bug this sprint fixes).
    _, conversation = _setup_business_without_kb(db_session)
    spy = _SpyProvider()

    response, retrieved, plan = generate_reply(db_session, conversation, "Hi", llm=spy)

    assert response.text == "Hello! I'm HIRA."
    assert retrieved == []
    assert len(spy.calls) == 1
    assert spy.calls[0]["tools"] is None
    assert "Answer ONLY using the information" not in spy.calls[0]["system"]


def test_generate_reply_returns_the_plan_it_actually_used_for_a_grounded_turn(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Sure, checking our calendar.")

    _, _, plan = generate_reply(
        db_session,
        conversation,
        "Book a meeting with John tomorrow at 3 PM.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert plan.category.value == "action"
    assert len(plan.steps) == 1
    assert plan.steps[0].domain == "calendar"


def test_generate_reply_returns_an_empty_steps_plan_for_demo_mode(db_session):
    """Sprint 76: the Demo Mode branch (no Business Knowledge yet) never
    runs planning at all — recomputing build_execution_plan() in a caller
    would misrepresent that turn as having offered tools it never did. The
    plan generate_reply() returns here must have empty steps regardless of
    what the message *would* have planned to, while still reflecting Stage 1
    classification for tracing (Sprint 76's execution_traces)."""
    _, conversation = _setup_business_without_kb(db_session)
    spy = _SpyProvider()

    _, _, plan = generate_reply(
        db_session, conversation, "Book a meeting with John tomorrow at 3 PM.", llm=spy
    )

    assert plan.steps == ()
    assert plan.category.value == "action"  # Stage 1 still classifies it


def test_generate_reply_uses_normal_prompt_once_knowledge_exists(db_session):
    # Sprint 55, requirement 8: existing behaviour must be untouched the
    # moment Business Knowledge exists — same grounded prompt as before this
    # sprint. (Sprint 57 narrowed which *tools* accompany it — see the
    # dedicated tool-routing tests below — but the prompt itself, and KB
    # retrieval, are unaffected by that change.)
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="We're open 9am-5pm on weekdays.")

    response, retrieved, plan = generate_reply(
        db_session, conversation, "what are your hours?", llm=spy, embedding=FakeEmbeddingProvider()
    )

    assert response.text == "We're open 9am-5pm on weekdays."
    assert len(retrieved) >= 1
    assert len(spy.calls) == 1
    assert "Answer ONLY using the information" in spy.calls[0]["system"]


# --- Sprint 57: intent-gated tool exposure ---------------------------------
#
# Business Knowledge exists in every test below (has_knowledge=True), so
# these exercise the *narrowing* generate_reply() now applies on top of the
# already-existing grounded branch — never the has_knowledge=False Demo Mode
# branch, which is covered separately above and is untouched by this sprint.


def test_generate_reply_offers_no_tools_for_a_knowledge_question(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="We're open 9am-5pm on weekdays.")

    generate_reply(
        db_session,
        conversation,
        "what are your business hours?",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []


def test_generate_reply_offers_no_tools_for_a_capability_question(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="I can check availability and book appointments for you.")

    generate_reply(
        db_session,
        conversation,
        "Can you schedule meetings?",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []


def test_generate_reply_offers_no_tools_for_a_greeting(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Hi there!")

    generate_reply(db_session, conversation, "Hi", llm=spy, embedding=FakeEmbeddingProvider())

    assert spy.calls[0]["tools"] == []


def test_generate_reply_offers_only_calendar_tools_for_a_booking_action(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Sure, checking our calendar.")

    # Sprint 58: a bare "Book a meeting tomorrow" (no time) is now held back
    # by the Action Readiness Check — see test_planning.py — so this needs a
    # complete request to reach Stage 2's tool selection at all.
    generate_reply(
        db_session,
        conversation,
        "Book a meeting tomorrow at 3pm",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }


def test_generate_reply_offers_only_crm_tools_for_a_lead_action(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Got it, logging that lead.")

    generate_reply(
        db_session,
        conversation,
        "Create a lead for John",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {CREATE_LEAD, UPDATE_LEAD_STAGE, SET_LEAD_FOLLOW_UP}


# --- Sprint 75 (DEC-045): cross-employee planning at the generate_reply level -


def test_generate_reply_offers_both_domains_tools_for_a_two_domain_message(db_session):
    """The end-to-end proof that Sprint 75 actually widened what the model
    is offered — not just that app/ai/plan.py's unit tests are internally
    consistent."""
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Done — both taken care of.")

    generate_reply(
        db_session,
        conversation,
        "Book a meeting tomorrow at 3pm and create a lead for John",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
        CREATE_LEAD,
        UPDATE_LEAD_STAGE,
        SET_LEAD_FOLLOW_UP,
    }


def test_generate_reply_still_offers_only_one_domain_for_a_single_domain_message(db_session):
    """Regression guard, at this exact call boundary, for acceptance
    criterion 9 — identical assertion to the pre-Sprint-75 booking test
    above, just naming the sprint that must not have changed it."""
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Sure, checking our calendar.")

    generate_reply(
        db_session,
        conversation,
        "Book a meeting tomorrow at 3pm",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }


# --- Sprint 58: Action Readiness Check (planning.py) -----------------------


def test_generate_reply_withholds_tools_and_asks_for_missing_date(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Sure — what date works for you?")

    generate_reply(
        db_session,
        conversation,
        "Book a meeting.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []
    assert "what date this should be on" in spy.calls[0]["system"]


def test_generate_reply_withholds_tools_and_asks_for_missing_time(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="What time works best?")

    generate_reply(
        db_session,
        conversation,
        "Book a meeting with John tomorrow.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []
    assert "what time this should be at" in spy.calls[0]["system"]


def test_generate_reply_offers_tools_once_booking_is_complete(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Great, checking availability now.")

    generate_reply(
        db_session,
        conversation,
        "Book a meeting with John tomorrow at 3 PM.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }
    assert "Action planning" not in spy.calls[0]["system"]


def test_generate_reply_withholds_tools_and_asks_for_lead_name(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Sure — who's the lead?")

    generate_reply(
        db_session,
        conversation,
        "Create a lead.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []
    assert "the customer's name" in spy.calls[0]["system"]


def test_generate_reply_withholds_tools_and_asks_which_appointment_to_cancel(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Which appointment would you like to cancel?")

    generate_reply(
        db_session,
        conversation,
        "Cancel my appointment.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []
    assert "which appointment" in spy.calls[0]["system"]


# --- Sprint 59: execution governance ----------------------------------------


def test_generate_reply_requires_confirmation_before_cancelling_a_specified_appointment(db_session):
    # Unlike test_generate_reply_withholds_tools_and_asks_which_appointment_
    # to_cancel above, this message *is* ready (it names which appointment)
    # — so this exercises governance's REQUIRES_CONFIRMATION policy, not
    # Sprint 58's readiness gate.
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(
        fixed_reply="Just to confirm, you'd like me to cancel tomorrow's appointment?"
    )

    generate_reply(
        db_session,
        conversation,
        "Cancel tomorrow's meeting",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []
    assert "confirm" in spy.calls[0]["system"].lower()
    assert "cancel" in spy.calls[0]["system"].lower()


def test_generate_reply_requires_confirmation_before_rescheduling(db_session):
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Just to confirm, move it to tomorrow at 10am?")

    generate_reply(
        db_session,
        conversation,
        "Reschedule my appointment to tomorrow at 10am.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    assert spy.calls[0]["tools"] == []
    assert "confirm" in spy.calls[0]["system"].lower()


def test_generate_reply_still_executes_a_ready_booking_immediately(db_session):
    # Regression: EXECUTE_NOW must not add any governance friction on top
    # of Sprint 58's existing "ready" path.
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Great, checking availability now.")

    generate_reply(
        db_session,
        conversation,
        "Book a meeting with John tomorrow at 3 PM.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }
    assert "Action planning" not in spy.calls[0]["system"]


def test_generate_reply_leaves_an_unrecognised_action_unmodified_by_governance(db_session):
    # Sprint 58's own "unsupported action passes through unmodified" case
    # (no ActionProfile matches, so plan.action is None) must not suddenly
    # get blocked now that governance exists — governance only ever runs
    # for a *named* action.
    _, conversation = _setup_business_with_kb(db_session)
    spy = _SpyProvider(fixed_reply="Sure, let me look into that.")

    generate_reply(
        db_session,
        conversation,
        "Update my appointment details.",
        llm=spy,
        embedding=FakeEmbeddingProvider(),
    )

    tool_names = {schema.name for schema in spy.calls[0]["tools"]}
    assert tool_names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }


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

    response, _, _ = generate_reply(
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

    response, _, _ = generate_reply(
        db_session,
        conversation,
        # Sprint 58: needs a concrete time too, or the Action Readiness
        # Check would withhold tools before this round trip ever starts —
        # see test_planning.py for that behaviour on its own.
        "can I book tuesday at 9am?",
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

    processing.generate_and_store_reply(conversation.id, None, "are you open today?")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].status == "pending_approval"
    assert outbound[0].body == "Yes, we're open today!"
    assert outbound[0].ai_meta["model"] == "mock-1"


def test_generate_and_store_reply_records_an_execution_trace(db_session, monkeypatch):
    """Sprint 76, Objective A: every turn through the real background
    processor gets a matching ExecutionTrace row, atomically alongside the
    Message it produced."""
    from app.models import ExecutionTrace

    biz, conversation = _setup_business_with_kb(db_session)
    trigger = Message(
        conversation_id=conversation.id,
        business_id=biz.id,
        direction="inbound",
        body="are you open today?",
        status="received",
    )
    db_session.add(trigger)
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="Yes, we're open today!"),
    )

    processing.generate_and_store_reply(conversation.id, trigger.id, "are you open today?")

    traces = db_session.scalars(
        select(ExecutionTrace).where(ExecutionTrace.conversation_id == conversation.id)
    ).all()
    assert len(traces) == 1
    trace = traces[0]
    assert trace.business_id == biz.id
    assert trace.trigger_message_id == trigger.id
    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).one()
    assert trace.result_message_ids == [str(outbound.id)]
    assert trace.duration_ms >= 0


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
    processing.generate_and_store_reply(conversation.id, None, "")

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

    processing.generate_and_store_reply(conversation_id, None, "are you open today?")

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

    processing.generate_and_store_reply(conversation.id, None, "book me tuesday at 2pm")

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

    processing.generate_and_store_reply(conversation.id, None, "I'd like a quote please")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].type == "tool_call"
    assert outbound[0].status == "pending_approval"
    assert outbound[0].ai_meta["tool_name"] == CREATE_LEAD
    from app.models import Lead

    assert db_session.scalars(select(Lead)).first() is None  # nothing written yet


# --- Sprint 74 Phase 1 (DEC-043): two-action collaboration ------------------


def test_assisted_mode_stores_two_proposed_actions_as_independent_pending_messages(
    db_session, monkeypatch
):
    """The Employee Registry attributes each action to its owning role, and
    each remains its own independently governed, independently approvable
    Message — a founder can approve one and reject the other."""
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
    booking = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    lead = ToolCall(id="2", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking, lead]),
    )

    processing.generate_and_store_reply(
        conversation.id, None, "book me tuesday and I'm ready to sign up"
    )

    outbound = db_session.scalars(
        select(Message).where(Message.direction == "outbound").order_by(Message.created_at)
    ).all()
    assert len(outbound) == 2
    assert outbound[0].type == "tool_call"
    assert outbound[0].status == "pending_approval"
    assert outbound[0].ai_meta["tool_name"] == BOOK_APPOINTMENT
    assert outbound[0].ai_meta["agent_role"] == "scheduler"
    assert outbound[1].type == "tool_call"
    assert outbound[1].status == "pending_approval"
    assert outbound[1].ai_meta["tool_name"] == CREATE_LEAD
    assert outbound[1].ai_meta["agent_role"] == "sales_executive"


def test_autonomous_mode_executes_two_actions_sequentially_not_in_parallel(db_session, monkeypatch):
    """Both actions execute and send in the order the model proposed them —
    sequential, not concurrent (no threads/async gather introduced)."""
    from app.models import Customer, Lead

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    _connect_whatsapp(db_session, monkeypatch, biz.id)
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    booking = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    lead = ToolCall(id="2", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking, lead]),
    )
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )
    send_order: list[str] = []

    def fake_sender(phone_number_id, to, body, **_kwargs):
        send_order.append(body)
        return f"wamid.{len(send_order)}"

    processing.generate_and_store_reply(
        conversation.id, None, "book me tuesday and I'm ready to sign up", sender=fake_sender
    )

    outbound = db_session.scalars(
        select(Message).where(Message.direction == "outbound").order_by(Message.created_at)
    ).all()
    assert len(outbound) == 2
    assert [m.status for m in outbound] == ["sent", "sent"]
    assert [m.ai_meta["agent_role"] for m in outbound] == ["scheduler", "sales_executive"]
    # Sent in the same order the actions were proposed and persisted —
    # sequential execution, not parallel (order would be nondeterministic
    # under real concurrent execution).
    assert send_order == [outbound[0].body, outbound[1].body]
    # Shared CRM memory (Objective D): the Lead created by the second action
    # references the exact same Customer the booking's Appointment does —
    # one source of truth, not a per-employee copy.
    created_lead = db_session.scalars(select(Lead)).first()
    assert created_lead is not None
    assert created_lead.customer_id == customer.id


def test_single_text_reply_is_attributed_to_the_receptionist(db_session, monkeypatch):
    """Text-only replies (no tool call) still carry attribution — every
    Message can show which employee handled it, not only tool-call ones."""
    from app.models import Customer

    biz = Business(name="Clinic A")
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

    processing.generate_and_store_reply(conversation.id, None, "are you open?")

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].ai_meta["agent_role"] == "receptionist"


# --- Sprint 75 (DEC-045): stop-on-failure sequential execution -------------


def test_autonomous_mode_stops_after_a_failed_action_and_never_attempts_the_next(
    db_session, monkeypatch
):
    """Objective D: if the first of two planned actions fails, the second
    (which may have been proposed on the assumption the first succeeded)
    must never be attempted — no Message row, no Lead row, nothing."""
    from app.models import Customer, Lead

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    _connect_whatsapp(db_session, monkeypatch, biz.id)
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db_session.add(customer)
    db_session.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db_session.add(conversation)
    db_session.flush()
    db_session.commit()

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(processing, "SessionLocal", test_sessionmaker)
    booking = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    lead = ToolCall(id="2", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking, lead]),
    )

    def _raise_not_connected(db, business_id):
        raise CalendarNotConnectedError("not connected")

    monkeypatch.setattr("app.ai.tools.get_appointment_service", _raise_not_connected)
    sends: list[str] = []

    def fake_sender(phone_number_id, to, body, **_kwargs):
        sends.append(body)
        return f"wamid.{len(sends)}"

    processing.generate_and_store_reply(
        conversation.id, None, "book me tuesday and I'm ready to sign up", sender=fake_sender
    )

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1  # the lead action's Message was never created
    assert outbound[0].ai_meta["tool_name"] == BOOK_APPOINTMENT
    assert outbound[0].status == "failed"
    assert sends == []  # nothing was sent to the customer either
    assert db_session.scalars(select(Lead)).first() is None  # the CRM write never ran


def test_autonomous_mode_executes_lead_tool_call_immediately(db_session, monkeypatch):
    from app.models import Customer, Lead

    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()
    _connect_whatsapp(db_session, monkeypatch, biz.id)
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

    def fake_sender(phone_number_id, to, body, **_kwargs):
        sent.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.sent1"

    processing.generate_and_store_reply(
        conversation.id, None, "I'd like a quote please", sender=fake_sender
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
    _connect_whatsapp(db_session, monkeypatch, biz.id)
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

    def fake_sender(phone_number_id, to, body, **_kwargs):
        sent.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.sent1"

    processing.generate_and_store_reply(conversation.id, None, "are you open?", sender=fake_sender)

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
    _connect_whatsapp(db_session, monkeypatch, biz.id)
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

    def fake_sender(phone_number_id, to, body, **_kwargs):
        sent.update(phone_number_id=phone_number_id, to=to, body=body)
        return "wamid.sent1"

    processing.generate_and_store_reply(
        conversation.id, None, "book me tuesday at 2pm", sender=fake_sender
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
    _connect_whatsapp(db_session, monkeypatch, biz.id)
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

    def fake_sender(phone_number_id, to, body, **_kwargs):
        sender_called["called"] = True
        return "wamid.sent1"

    processing.generate_and_store_reply(
        conversation.id, None, "book me tuesday at 2pm", sender=fake_sender
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
    _connect_whatsapp(db_session, monkeypatch, biz.id)
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
        lambda db, business_id: AppointmentService(
            db, business_id, provider, calendar_id="primary"
        ),
    )
    sent = {"count": 0}

    def fake_sender(phone_number_id, to, body, **_kwargs):
        sent["count"] += 1
        return f"wamid.out{sent['count']}"

    processing.generate_and_store_reply(
        conversation_id, None, "book me tuesday at 2pm", sender=fake_sender
    )

    # Nothing durably persisted -- no stale pending Message, no orphaned Appointment.
    assert (
        db_session.scalars(select(Message).where(Message.conversation_id == conversation_id)).all()
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
        conversation_id, None, "book me tuesday at 2pm", sender=fake_sender
    )

    appointments = db_session.scalars(select(Appointment)).all()
    assert len(appointments) == 1
