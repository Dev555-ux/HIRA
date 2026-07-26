"""Tests for the AI Playground: reuses generate_reply(), never duplicates it."""

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
    """A proposed booking with no Google Calendar connected must not look
    like a silent failure or a fake success — the tool's own honest reason
    becomes the chat reply, same as it would for a real WhatsApp customer."""
    from app.ai.llm.base import ToolCall
    from app.ai.tools import BOOK_APPOINTMENT

    biz = _business(db_session)
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
    assert body == "This business has not connected a Google Calendar"

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
    Chat's own execution path."""
    from app.ai.llm.base import ToolCall
    from app.ai.lead_tools import CREATE_LEAD
    from app.ai.tools import BOOK_APPOINTMENT
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
    # No AppointmentService/CalendarProvider monkeypatch — the booking fails
    # with the same honest "no calendar connected" error as the test above.

    response, _, body, tool_outcome = playground_reply(
        db_session, biz.id, "book me tuesday and sign me up"
    )

    assert tool_outcome == {"name": BOOK_APPOINTMENT, "success": False}
    assert body == "This business has not connected a Google Calendar"

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
