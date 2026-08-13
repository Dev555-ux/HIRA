"""Tests for the AI Playground: reuses generate_reply(), never duplicates it."""

from datetime import datetime, timedelta

from app.ai.knowledge_base import index_entry
from app.ai.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse, ToolSchema
from app.ai.llm.mock import MockProvider
from app.ai.playground import (
    LLM_UNAVAILABLE_TEXT,
    PLAYGROUND_PHONE,
    get_or_create_playground_conversation,
    playground_reply,
)
from app.models import Business, Conversation, Customer, Message
from tests.test_knowledge_base import FakeEmbeddingProvider


def _tomorrow_at(hour: int, minute: int = 0) -> str:
    """A same-shape-as-hardcoded ISO datetime that's always in the future
    relative to whenever the suite runs, so "upcoming appointment" lookups
    (app/calendar/service.py::get_upcoming_appointments) find what these
    tests just booked regardless of what today's date happens to be — a
    literal hardcoded date rots into the past the moment "today" catches up
    to it (see tests fixed by this helper)."""
    tomorrow = datetime.now() + timedelta(days=1)
    return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0).isoformat(
        timespec="seconds"
    )


class FailingProvider(LLMProvider):
    """Simulates Groq's real tool_use_failed 400 (a malformed function call) —
    the exact live crash Demo Chat previously let propagate as an unhandled
    500 instead of a chat reply."""

    def generate(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int | None = None,
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        raise LLMError("Groq rejected the request: tool_use_failed")


def _business(db, name="Clinic A"):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def _mock_llm_and_embeddings(monkeypatch, *, fixed_reply="Mock reply"):
    """playground_reply() calls the unmodified generate_reply(), which resolves
    providers via the module-level factories — patch those, exactly like
    test_orchestrator.py does, rather than adding a provider param that would
    change generate_reply()'s signature."""
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply=fixed_reply),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )


def test_get_or_create_playground_conversation_is_idempotent(db_session):
    biz = _business(db_session)

    first = get_or_create_playground_conversation(db_session, biz.id)
    second = get_or_create_playground_conversation(db_session, biz.id)

    assert first.id == second.id
    customers = db_session.query(Customer).filter_by(business_id=biz.id).all()
    assert len(customers) == 1
    assert customers[0].wa_phone == PLAYGROUND_PHONE


def test_playground_reply_reuses_kb_retrieval_and_persists_turn(db_session, monkeypatch):
    biz = _business(db_session)
    index_entry(
        db_session, biz.id, "Hours", "We are open 9am to 5pm.", provider=FakeEmbeddingProvider()
    )
    _mock_llm_and_embeddings(monkeypatch, fixed_reply="We're open 9-5!")

    response, retrieved, body, tool_outcome = playground_reply(
        db_session, biz.id, "what are your hours?"
    )
    assert tool_outcome is None

    assert response.text == "We're open 9-5!"
    assert body == "We're open 9-5!"
    assert len(retrieved) >= 1
    assert any("9am" in e.content for e in retrieved)

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    messages = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    assert [m.direction for m in messages] == ["inbound", "outbound"]
    assert messages[0].body == "what are your hours?"
    assert messages[1].body == "We're open 9-5!"
    assert messages[1].status == "sent"  # no Assisted-Mode approval gate in the playground


def test_playground_accumulates_history_across_turns(db_session, monkeypatch):
    biz = _business(db_session)
    _mock_llm_and_embeddings(monkeypatch, fixed_reply="ok")

    playground_reply(db_session, biz.id, "first question")
    playground_reply(db_session, biz.id, "second question")

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    messages = db_session.query(Message).filter_by(conversation_id=conversation.id).all()
    assert len(messages) == 4  # two full turns, same conversation


def test_playground_is_tenant_scoped(db_session, monkeypatch):
    biz_a = _business(db_session, "Clinic A")
    biz_b = _business(db_session, "Clinic B")
    _mock_llm_and_embeddings(monkeypatch)

    playground_reply(db_session, biz_a.id, "hello from A")

    conv_a = get_or_create_playground_conversation(db_session, biz_a.id)
    conv_b = get_or_create_playground_conversation(db_session, biz_b.id)
    assert conv_a.id != conv_b.id
    assert db_session.query(Message).filter_by(conversation_id=conv_b.id).count() == 0


def test_playground_does_not_touch_real_customer_conversations(db_session, monkeypatch):
    biz = _business(db_session)
    real_customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db_session.add(real_customer)
    db_session.flush()
    real_conversation = Conversation(business_id=biz.id, customer_id=real_customer.id)
    db_session.add(real_conversation)
    db_session.flush()
    _mock_llm_and_embeddings(monkeypatch)

    playground_reply(db_session, biz.id, "test message")

    assert db_session.query(Message).filter_by(conversation_id=real_conversation.id).count() == 0


def test_playground_reply_falls_back_gracefully_on_llm_error(db_session, monkeypatch):
    biz = _business(db_session)
    monkeypatch.setattr("app.ai.orchestrator.get_llm_provider", lambda name=None: FailingProvider())
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )

    response, retrieved, body, tool_outcome = playground_reply(
        db_session, biz.id, "do you have slots free this friday?"
    )

    assert body == LLM_UNAVAILABLE_TEXT
    assert response.text == LLM_UNAVAILABLE_TEXT
    assert retrieved == []
    assert tool_outcome is None

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    messages = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    # The turn is still persisted (inbound + a resolved outbound fallback) —
    # not silently dropped, and not left as a half-written transaction.
    assert [m.direction for m in messages] == ["inbound", "outbound"]
    assert messages[1].body == LLM_UNAVAILABLE_TEXT
    assert messages[1].status == "sent"


def test_playground_reply_records_the_real_plan_when_the_llm_call_fails_after_planning(
    db_session, monkeypatch
):
    """Sprint 80 follow-up (live production smoke test): if a real plan was
    already computed — Business Knowledge exists, so the message went
    through build_execution_plan and decided to offer calendar tools —
    before the LLM call itself throws (e.g. Groq's tool_use_failed), the
    ExecutionTrace must still reflect that plan, not silently downgrade to
    an empty conversation plan. Previously it always downgraded regardless
    of what was actually decided, which made Founder Ops' Execution Trace
    read "No tools were offered for this turn" even on a turn where 4
    calendar tools genuinely were offered and only the LLM provider call
    itself failed."""
    from app.models import ExecutionTrace

    biz = _business(db_session)
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )
    monkeypatch.setattr("app.ai.orchestrator.get_llm_provider", lambda name=None: FailingProvider())
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )

    response, retrieved, body, tool_outcome = playground_reply(
        db_session, biz.id, "I'd like a teeth cleaning tomorrow around 3 PM"
    )

    assert body == LLM_UNAVAILABLE_TEXT
    assert tool_outcome is None

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    trace = db_session.query(ExecutionTrace).filter_by(conversation_id=conversation.id).one()
    assert trace.category == "action"
    assert trace.plan["active_domain"] == "calendar"
    assert trace.plan["steps"][0]["domain"] == "calendar"
    assert trace.proposed_tool_calls == []


def test_playground_executes_a_proposed_lead_tool_call_for_real(db_session, monkeypatch):
    """Demo Chat sprint: unlike WhatsApp's Assisted Mode (held for approval)
    or the old playground (preview only), a proposed tool call now actually
    executes — there is no human reviewer on a demo conversation, so holding
    it for an approval that will never come would be a dead end. Reuses
    execute_tool_call() exactly as Autonomous Mode's _auto_send does."""
    from app.ai.llm.base import ToolCall
    from app.ai.lead_tools import CREATE_LEAD
    from app.models import Lead

    biz = _business(db_session)
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "Demo Chat"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )

    response, _, body, tool_outcome = playground_reply(db_session, biz.id, "I'd like a quote")

    assert response.text == ""
    assert tool_outcome == {"name": CREATE_LEAD, "success": True}
    assert body == "Thanks — that's been taken care of."  # confirmation_message_for's CRM text

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id, direction="outbound")
        .first()
    )
    assert outbound.type == "text"  # resolved, not left as an internal tool_call preview
    assert outbound.body == body

    lead = db_session.query(Lead).filter_by(business_id=biz.id).first()
    assert lead is not None
    assert lead.source == "Demo Chat"


def test_playground_executes_two_proposed_actions_sequentially(db_session, monkeypatch):
    """Sprint 74 Phase 1 (DEC-043): both actions execute for real and both
    persist their own Message, attributed to their owning employee — the
    API/UI contract stays unchanged (one body/tool_outcome returned,
    reflecting the last action), but nothing is lost server-side."""
    from app.ai.llm.base import ToolCall
    from app.ai.lead_tools import CREATE_LEAD
    from app.ai.tools import BOOK_APPOINTMENT
    from app.calendar.providers.mock import MockCalendarProvider
    from app.calendar.service import AppointmentService
    from app.models import Lead

    biz = _business(db_session)
    booking = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    lead = ToolCall(id="2", name=CREATE_LEAD, arguments={"source": "Demo Chat"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking, lead]),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )

    response, _, body, tool_outcome = playground_reply(
        db_session, biz.id, "book me tuesday and sign me up"
    )

    # Return value reflects the last action (the API/UI contract is
    # unchanged — one bubble per turn).
    assert tool_outcome == {"name": CREATE_LEAD, "success": True}
    assert body == "Thanks — that's been taken care of."

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id, direction="outbound")
        .order_by(Message.created_at)
        .all()
    )
    assert len(outbound) == 2
    assert outbound[0].ai_meta["agent_role"] == "scheduler"
    assert outbound[0].ai_meta["tool_result"] == "Appointment booked."
    assert outbound[1].ai_meta["agent_role"] == "sales_executive"
    assert outbound[1].ai_meta["tool_result"] == "Lead logged."
    assert db_session.query(Lead).filter_by(business_id=biz.id).first() is not None


def test_playground_reports_an_honest_failure_for_a_tool_call_that_cant_execute(
    db_session, monkeypatch
):
    """A proposed booking for a slot that's already taken must not look like
    a silent failure or a fake success — the tool's own honest reason becomes
    the chat reply, same as it would for a real WhatsApp customer.

    Sprint 78: a missing Google Calendar connection no longer makes booking
    fail (see app/calendar/factory.py's InternalSchedulerProvider fallback),
    so this now exercises a genuine failure mode that still exists under the
    internal scheduler — a real slot conflict."""
    from datetime import datetime

    from app.ai.llm.base import ToolCall
    from app.ai.tools import BOOK_APPOINTMENT
    from app.models import Appointment, Customer

    biz = _business(db_session)
    blocker_customer = Customer(business_id=biz.id, wa_phone="+15550009999")
    db_session.add(blocker_customer)
    db_session.flush()
    db_session.add(
        Appointment(
            business_id=biz.id,
            customer_id=blocker_customer.id,
            google_event_id="internal-blocker",
            starts_at=datetime.fromisoformat("2026-08-05T14:00:00"),
            ends_at=datetime.fromisoformat("2026-08-05T15:00:00"),
            status="booked",
        )
    )
    db_session.flush()

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
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )

    response, _, body, tool_outcome = playground_reply(db_session, biz.id, "book me tuesday at 2pm")

    assert response.text == ""
    assert tool_outcome == {"name": BOOK_APPOINTMENT, "success": False}
    assert body == "Requested slot overlaps an existing appointment"

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id, direction="outbound")
        .first()
    )
    assert outbound.type == "text"
    assert outbound.body == body


def test_playground_stops_after_a_failed_action_and_never_attempts_the_next(
    db_session, monkeypatch
):
    """Sprint 75, Objective D — same stop-on-failure guarantee as Autonomous
    Mode's identical test in test_orchestrator.py, exercised through Demo
    Chat's own execution path.

    Sprint 78: a missing Google Calendar connection no longer makes booking
    fail (InternalSchedulerProvider fallback), so this now uses a genuine
    slot conflict to exercise the same stop-on-failure guarantee."""
    from datetime import datetime

    from app.ai.llm.base import ToolCall
    from app.ai.lead_tools import CREATE_LEAD
    from app.ai.tools import BOOK_APPOINTMENT
    from app.models import Appointment, Customer, Lead

    biz = _business(db_session)
    blocker_customer = Customer(business_id=biz.id, wa_phone="+15550009999")
    db_session.add(blocker_customer)
    db_session.flush()
    db_session.add(
        Appointment(
            business_id=biz.id,
            customer_id=blocker_customer.id,
            google_event_id="internal-blocker",
            starts_at=datetime.fromisoformat("2026-08-05T14:00:00"),
            ends_at=datetime.fromisoformat("2026-08-05T15:00:00"),
            status="booked",
        )
    )
    db_session.flush()

    booking = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Cleaning",
        },
    )
    lead = ToolCall(id="2", name=CREATE_LEAD, arguments={"source": "Demo Chat"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking, lead]),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    # No AppointmentService/CalendarProvider monkeypatch — the booking fails
    # with the same genuine conflict as the test above.

    response, _, body, tool_outcome = playground_reply(
        db_session, biz.id, "book me tuesday and sign me up"
    )

    assert tool_outcome == {"name": BOOK_APPOINTMENT, "success": False}
    assert body == "Requested slot overlaps an existing appointment"

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id, direction="outbound")
        .all()
    )
    assert len(outbound) == 1  # the lead action was never attempted
    assert db_session.query(Lead).filter_by(business_id=biz.id).first() is None


def test_playground_reply_records_an_execution_trace(db_session, monkeypatch):
    """Sprint 76, Objective A: Demo Chat turns get an ExecutionTrace too,
    same as real WhatsApp turns — trigger_message_id is the synthetic
    inbound Message this turn created (get_or_create_playground_conversation
    has no separate webhook layer to hand one in from)."""
    from app.models import ExecutionTrace

    biz = _business(db_session)
    index_entry(
        db_session, biz.id, "Hours", "We are open 9am to 5pm.", provider=FakeEmbeddingProvider()
    )
    _mock_llm_and_embeddings(monkeypatch, fixed_reply="We're open 9-5!")

    playground_reply(db_session, biz.id, "what are your hours?")

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    trace = db_session.query(ExecutionTrace).filter_by(conversation_id=conversation.id).one()
    inbound, outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    assert trace.business_id == biz.id
    assert trace.trigger_message_id == inbound.id
    assert trace.result_message_ids == [str(outbound.id)]


def test_the_teeth_cleaning_demo_scenario_books_via_internal_scheduler_end_to_end(
    db_session, monkeypatch
):
    """Sprint 78 success criteria, exercised exactly as the live demo will
    run it through Demo Chat: 'I'd like a teeth cleaning tomorrow around
    3 PM' books successfully via InternalSchedulerProvider (no Google
    Calendar connected — none needed) and everything downstream (the
    Appointment row, Founder Dashboard's data, Execution Trace,
    Conversation Replay) reflects it exactly as it would for a
    Google-synced booking."""
    from datetime import datetime

    from app.ai.llm.base import ToolCall
    from app.ai.tools import BOOK_APPOINTMENT
    from app.models import Appointment, ExecutionTrace

    biz = _business(db_session)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T15:00:00",
            "ends_at": "2026-08-05T15:30:00",
            "summary": "Teeth cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[tool_call]),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )

    response, _, body, tool_outcome = playground_reply(
        db_session, biz.id, "I'd like a teeth cleaning tomorrow around 3 PM"
    )

    # Appointment Created — a real, persisted Appointment row, booked via
    # InternalSchedulerProvider with no external calendar involved.
    assert tool_outcome == {"name": BOOK_APPOINTMENT, "success": True}
    assert body == (
        "You're all set! Teeth cleaning is booked for 2026-08-05T15:00:00 to 2026-08-05T15:30:00."
    )
    appointment = db_session.query(Appointment).filter_by(business_id=biz.id).one()
    assert appointment.status == "booked"
    assert appointment.starts_at == datetime.fromisoformat("2026-08-05T15:00:00")
    assert appointment.google_event_id.startswith("internal-")

    # Founder Dashboard reflects the activity — get_upcoming_appointments is
    # exactly what the dashboard/appointments list reads from.
    from app.calendar.service import get_upcoming_appointments

    upcoming = get_upcoming_appointments(db_session, biz.id, appointment.customer_id)
    assert [a.id for a in upcoming] == [appointment.id]

    # Execution Trace records the workflow (intent -> availability check
    # implicit in the plan -> tool call -> result), same as any other turn.
    conversation = get_or_create_playground_conversation(db_session, biz.id)
    trace = db_session.query(ExecutionTrace).filter_by(conversation_id=conversation.id).one()
    assert trace.proposed_tool_calls == [
        {"tool_name": BOOK_APPOINTMENT, "agent_role": "scheduler"}
    ]

    # Conversation Replay shows the completed conversation — the real
    # inbound customer message and the real outbound confirmation.
    inbound, outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    assert inbound.body == "I'd like a teeth cleaning tomorrow around 3 PM"
    assert outbound.body == body
    assert outbound.status == "sent"


def test_sprint_80_reproduces_and_fixes_the_exact_reported_production_bug(db_session, monkeypatch):
    """The exact two-turn conversation from the live production bug report
    (DEC-049), reproduced end-to-end through the real orchestrator/planning
    pipeline — not just unit-level app/ai/plan.py assertions.

    Turn 1 deliberately uses a MockProvider that replies with *plain text
    only, no tool call* — the worst case, where the model narrates without
    acting, exactly as observed live. Before Sprint 80 this would also have
    had zero tools offered in the first place (Stage 1 never recognised
    "I'd like a teeth cleaning tomorrow around 3 PM" as ACTION at all); now
    tools are offered, and even though this particular canned reply still
    doesn't call one, the turn's ExecutionTrace correctly records
    active_domain="calendar" for turn 2 to inherit.

    Turn 2 is the customer's bare affirmative follow-up — the literal
    "Sure, please go ahead" from the bug report — with a MockProvider that
    now proposes book_appointment, proving the domain carried across turns
    and a real appointment gets booked, where before this reply would have
    gone entirely tools-less."""
    from app.ai.llm.base import ToolCall
    from app.ai.tools import BOOK_APPOINTMENT
    from app.calendar.service import get_upcoming_appointments
    from app.models import Appointment, ExecutionTrace

    biz = _business(db_session)
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    # Business Knowledge must be non-empty, or generate_reply() takes the
    # Demo Mode branch (app/ai/orchestrator.py) — which never calls
    # build_execution_plan()/offers any tools at all, real or inherited —
    # and this test would (as it initially did) pass for the wrong reason:
    # MockProvider returns whatever fixed_tool_calls it's given regardless
    # of whether the orchestrator actually offered any tools that turn.
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )

    # --- Turn 1: the original request, model replies in prose only -----
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(
            fixed_reply="I'll check availability for you — let me just check our schedule."
        ),
    )
    _, _, turn_1_body, turn_1_outcome = playground_reply(
        db_session, biz.id, "I'd like a teeth cleaning tomorrow around 3 PM."
    )
    assert turn_1_outcome is None  # no tool was called this turn — the reply is text-only

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    turn_1_trace = (
        db_session.query(ExecutionTrace)
        .filter_by(conversation_id=conversation.id)
        .order_by(ExecutionTrace.created_at)
        .first()
    )
    # This is the crux of the bug: tools *were* offered this turn (proven by
    # active_domain being set), not silently withheld — the model simply
    # chose not to call one, which is a legitimate model choice the next
    # turn's continuity now correctly compensates for.
    assert turn_1_trace.plan["category"] == "action"
    assert turn_1_trace.plan["active_domain"] == "calendar"
    assert turn_1_trace.proposed_tool_calls == []

    # --- Turn 2: the bare confirmation from the bug report --------------
    booking_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-06T15:00:00",
            "ends_at": "2026-08-06T15:30:00",
            "summary": "Teeth cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking_call]),
    )
    _, _, turn_2_body, turn_2_outcome = playground_reply(
        db_session, biz.id, "Sure, please go ahead."
    )

    assert turn_2_outcome == {"name": BOOK_APPOINTMENT, "success": True}
    assert "booked" in turn_2_body.lower()
    appointment = db_session.query(Appointment).filter_by(business_id=biz.id).one()
    assert appointment.status == "booked"

    # Founder Dashboard / Execution Trace / Conversation Replay all reflect
    # the real outcome, not the hallucinated one.
    upcoming = get_upcoming_appointments(db_session, biz.id, appointment.customer_id)
    assert [a.id for a in upcoming] == [appointment.id]

    turn_2_trace = (
        db_session.query(ExecutionTrace)
        .filter_by(conversation_id=conversation.id)
        .order_by(ExecutionTrace.created_at.desc())
        .first()
    )
    assert turn_2_trace.proposed_tool_calls == [
        {"tool_name": BOOK_APPOINTMENT, "agent_role": "scheduler"}
    ]

    messages = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at)
        .all()
    )
    assert [m.body for m in messages] == [
        "I'd like a teeth cleaning tomorrow around 3 PM.",
        "I'll check availability for you — let me just check our schedule.",
        "Sure, please go ahead.",
        turn_2_body,
    ]


def test_dec_051_a_cancellation_confirmation_that_echoes_its_own_trigger_word_resumes(
    db_session, monkeypatch
):
    """The follow-up bug found while re-verifying Sprint 80 live: cancel is
    a governance-gated action (app/ai/governance.py, REQUIRES_CONFIRMATION),
    so it always asks the customer to confirm first — but the *natural* way
    to confirm a cancellation ("Yes, cancel it.") contains the word "cancel",
    which is calendar_cancel's own trigger keyword. That match sent the
    confirmation text through app/ai/planning.py's required-field check a
    second time, which correctly-in-isolation found no appointment reference
    in the four-word reply and withheld the tool again — asking the same
    question forever, never actually cancelling anything.

    Reproduced end-to-end through the real orchestrator/planning/governance
    pipeline across three turns: book something real, ask to cancel it
    (governance withholds pending confirmation), then confirm in the exact
    words that used to defeat it."""
    from app.ai.llm.base import ToolCall
    from app.ai.tools import BOOK_APPOINTMENT, CANCEL_APPOINTMENT
    from app.models import Appointment, ExecutionTrace

    biz = _business(db_session)
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )

    # --- Turn 1: book something real, so there's an upcoming appointment -
    booking_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-06T14:00:00",
            "ends_at": "2026-08-06T14:30:00",
            "summary": "Teeth cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking_call]),
    )
    playground_reply(db_session, biz.id, "Book a teeth cleaning tomorrow at 2pm.")
    appointment = db_session.query(Appointment).filter_by(business_id=biz.id).one()
    assert appointment.status == "booked"

    conversation = get_or_create_playground_conversation(db_session, biz.id)

    # --- Turn 2: ask to cancel — governance withholds pending confirmation
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(
            fixed_reply="Just to confirm, you'd like to cancel your teeth cleaning tomorrow at 2pm?"
        ),
    )
    _, _, turn_2_body, turn_2_outcome = playground_reply(
        db_session, biz.id, "Actually please cancel my upcoming appointment."
    )
    assert turn_2_outcome is None

    turn_2_trace = (
        db_session.query(ExecutionTrace)
        .filter_by(conversation_id=conversation.id)
        .order_by(ExecutionTrace.created_at.desc())
        .first()
    )
    # Planning found the action fully specified ("upcoming" satisfies
    # appointment_reference); governance is what withheld it, recording
    # exactly which already-validated action the next turn should resume.
    assert turn_2_trace.plan["category"] == "action"
    assert turn_2_trace.plan["pending_action"] == "calendar_cancel"
    assert turn_2_trace.proposed_tool_calls == []

    # --- Turn 3: the exact confirmation phrasing that used to defeat this
    cancel_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[cancel_call]),
    )
    _, _, turn_3_body, turn_3_outcome = playground_reply(db_session, biz.id, "Yes, cancel it.")

    assert turn_3_outcome == {"name": CANCEL_APPOINTMENT, "success": True}
    assert "cancel" in turn_3_body.lower()
    db_session.refresh(appointment)
    assert appointment.status != "booked"

    turn_3_trace = (
        db_session.query(ExecutionTrace)
        .filter_by(conversation_id=conversation.id)
        .order_by(ExecutionTrace.created_at.desc())
        .first()
    )
    assert turn_3_trace.proposed_tool_calls == [
        {"tool_name": CANCEL_APPOINTMENT, "agent_role": "scheduler"}
    ]


def test_sprint_81_an_unrelated_disclosure_after_a_completed_booking_does_not_rebook(
    db_session, monkeypatch
):
    """The exact live-reproduced bug, end-to-end through the real
    orchestrator/planning pipeline (app/ai/plan.py::build_execution_plan(),
    not a direct unit call): a completed booking leaves calendar
    `active_domain` open for continuity (by design — see
    TestBookingClarification in tests/test_intent_continuity.py); an
    unrelated aside two turns later must not silently re-expose
    book_appointment. Before the fix (DEC-057), this turn offered all four
    calendar tools with no readiness check and no governance gate — neither
    book_appointment nor create_lead is in
    app/ai/tools.py::GOVERNED_TOOL_ACTIONS — and Demo Chat executes whatever
    the model proposes immediately, producing a second, real, unrequested
    Appointment row."""
    from app.ai.llm.base import ToolCall
    from app.ai.tools import BOOK_APPOINTMENT
    from app.models import Appointment

    biz = _business(db_session)
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )

    # --- Turn 1: book something real -------------------------------------
    booking_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": _tomorrow_at(15),
            "ends_at": _tomorrow_at(15, 30),
            "summary": "Teeth cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking_call]),
    )
    _, _, _, turn_1_outcome = playground_reply(
        db_session, biz.id, "I would like to book a teeth cleaning appointment tomorrow at 3pm"
    )
    assert turn_1_outcome == {"name": BOOK_APPOINTMENT, "success": True}
    assert db_session.query(Appointment).filter_by(business_id=biz.id).count() == 1

    # --- Turn 2: a follow-up question that re-touches the calendar domain
    # via its own keyword match ("book"/"appointment"), but isn't itself a
    # new booking request — planning correctly finds it not ready, which
    # (pre-fix) still left the domain "pending" for the next turn too.
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="I'm not sure about that, let me check."),
    )
    _, _, _, turn_2_outcome = playground_reply(
        db_session, biz.id, "What time did I just book my appointment for?"
    )
    assert turn_2_outcome is None

    # --- Turn 3: the unrelated disclosure — must NOT book again -----------
    # No fixed_tool_calls: a real LLM structurally cannot emit a tool call
    # for a tool it was never offered (build_execution_plan must return no
    # tools this turn) — MockProvider ignores the `tools` kwarg entirely, so
    # asserting no *fixed* tool call is configured, combined with asserting
    # no second Appointment was written, is what actually proves the tool
    # was withheld rather than merely unused.
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="Nice to meet you, Devansh!"),
    )
    _, _, turn_3_body, turn_3_outcome = playground_reply(
        db_session, biz.id, "My name is Devansh, just so you know."
    )

    assert turn_3_outcome is None
    assert turn_3_body == "Nice to meet you, Devansh!"
    assert db_session.query(Appointment).filter_by(business_id=biz.id).count() == 1, (
        "a second Appointment row was written — the reported bug regressed"
    )


def test_sprint_82_a_polite_lead_request_offers_the_tool_instead_of_hallucinating(
    db_session, monkeypatch
):
    """The exact live-reproduced bug: 'Can you log me as a lead?' used to
    classify as CAPABILITY (app/ai/intent.py::_CAPABILITY_MODAL_RE matched
    before any action rule got a chance), so no tool was ever offered — yet
    the model still replied "I've created a lead for you," and no Lead row
    was written. Reproduced end-to-end through the real orchestrator/
    planning pipeline: the ExecutionTrace's own plan is checked (not just
    the mocked reply) to prove the tool was genuinely offered this turn,
    not merely that the mock happened to be configured with one."""
    from app.ai.lead_tools import CREATE_LEAD
    from app.ai.llm.base import ToolCall
    from app.models import ExecutionTrace, Lead

    biz = _business(db_session)
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )

    lead_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[lead_call]),
    )

    _, _, body, tool_outcome = playground_reply(
        db_session, biz.id, "Can you log me as a lead?"
    )

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    trace = (
        db_session.query(ExecutionTrace)
        .filter_by(conversation_id=conversation.id)
        .order_by(ExecutionTrace.created_at.desc())
        .first()
    )
    assert trace.plan["category"] == "action"
    assert any("create_lead" in step["tools"] for step in trace.plan["steps"]), (
        "create_lead was not offered this turn — the request was misclassified again"
    )

    # And the tool actually executed for real — no fabricated confirmation.
    assert tool_outcome == {"name": CREATE_LEAD, "success": True}
    lead = db_session.query(Lead).filter_by(business_id=biz.id).first()
    assert lead is not None
    assert lead.source == "WhatsApp inquiry"


def test_sprint_82_no_false_success_when_the_model_declines_to_call_the_offered_tool(
    db_session, monkeypatch
):
    """The safety-net half of the fix: even when create_lead IS correctly
    offered, the model must never be structurally trusted to have called it
    just because a customer asked. Here the tool is offered (as proven via
    the trace, same as the test above) but the mock model responds with
    plain text only — playground.py must report tool_outcome=None and the
    reply must be exactly the model's own text, not a fabricated confirmation
    stitched in by anything downstream. Combined with the safeguard now in
    app/ai/prompts.py::build_system_prompt (tested directly in
    tests/test_prompts.py), this is what stops a future misclassification
    from reproducing the original bug even before it's diagnosed."""
    from app.models import Lead

    biz = _business(db_session)
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="Sure, what's your name and number?"),
    )

    _, _, body, tool_outcome = playground_reply(db_session, biz.id, "Can you log me as a lead?")

    assert tool_outcome is None
    assert body == "Sure, what's your name and number?"
    assert db_session.query(Lead).filter_by(business_id=biz.id).count() == 0


def test_sprint_82_third_party_lead_creation_still_works_unchanged(db_session, monkeypatch):
    """Naming someone else ("Create a lead for Priya") is a separate, already
    -working path (own Stage 2 domain match via the "lead" keyword, not this
    fix's capability/action boundary) — confirms it's untouched."""
    from app.ai.lead_tools import CREATE_LEAD
    from app.ai.llm.base import ToolCall
    from app.models import Lead

    biz = _business(db_session)
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )
    index_entry(
        db_session,
        biz.id,
        "Services",
        "We offer teeth cleaning appointments.",
        provider=FakeEmbeddingProvider(),
    )
    lead_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"notes": "Interested, ask for Priya"})
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[lead_call]),
    )

    _, _, _, tool_outcome = playground_reply(db_session, biz.id, "Create a lead for Priya.")

    assert tool_outcome == {"name": CREATE_LEAD, "success": True}
    assert db_session.query(Lead).filter_by(business_id=biz.id).count() == 1
