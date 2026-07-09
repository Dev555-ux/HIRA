"""Tests for app/ai/context.py: the Context Builder assembles business,
customer, lead, upcoming-appointment, knowledge-base, and summary information
into one ConversationContext (DEC-034)."""

from datetime import datetime, timedelta, timezone

from app.ai.context import build_context, load_history
from app.ai.knowledge_base import index_entry
from app.ai.llm.mock import MockProvider
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.models import Business, Conversation, Customer, Message
from app.services.leads import create_lead
from tests.test_knowledge_base import FakeEmbeddingProvider

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


def _conversation(db, *, display_name="Alex Rivera"):
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000", display_name=display_name)
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db.add(conversation)
    db.flush()
    db.commit()
    return biz, customer, conversation


def test_build_context_includes_business_and_customer(db_session):
    biz, customer, conversation = _conversation(db_session)

    context = build_context(db_session, conversation, "hi there", llm=MockProvider())

    assert context.business.id == biz.id
    assert context.customer.id == customer.id


def test_build_context_includes_the_customers_lead(db_session):
    biz, customer, conversation = _conversation(db_session)
    lead = create_lead(db_session, biz.id, customer.id, stage="qualified")

    context = build_context(db_session, conversation, "hi there", llm=MockProvider())

    assert context.lead is not None
    assert context.lead.id == lead.id
    assert context.lead.stage == "qualified"


def test_build_context_lead_is_none_when_customer_has_no_lead(db_session):
    _, _, conversation = _conversation(db_session)

    context = build_context(db_session, conversation, "hi there", llm=MockProvider())

    assert context.lead is None


def test_build_context_includes_upcoming_appointments(db_session):
    biz, customer, conversation = _conversation(db_session)
    service = AppointmentService(db_session, biz.id, MockCalendarProvider(), calendar_id="primary")
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=conversation.id,
        starts_at=NOW + timedelta(days=1),
        ends_at=NOW + timedelta(days=1, minutes=30),
        summary="Cleaning",
    )

    context = build_context(db_session, conversation, "hi there", llm=MockProvider())

    assert [a.id for a in context.upcoming_appointments] == [appointment.id]


def test_build_context_includes_retrieved_kb_entries(db_session):
    biz, _, conversation = _conversation(db_session)
    index_entry(
        db_session,
        biz.id,
        "Hours",
        "We are open 9am to 5pm on weekdays.",
        provider=FakeEmbeddingProvider(),
    )

    context = build_context(
        db_session,
        conversation,
        "We are open 9am to 5pm on weekdays.",
        llm=MockProvider(),
        embedding=FakeEmbeddingProvider(),
    )

    assert len(context.retrieved_kb) == 1
    assert context.retrieved_kb[0].title == "Hours"


def test_build_context_includes_recent_history(db_session):
    _, _, conversation = _conversation(db_session)
    db_session.add(
        Message(
            conversation_id=conversation.id,
            business_id=conversation.business_id,
            direction="inbound",
            body="earlier message",
            status="received",
        )
    )
    db_session.commit()

    context = build_context(db_session, conversation, "hi there", llm=MockProvider())

    assert len(context.history) == 1
    assert context.history[0].body == "earlier message"


def test_load_history_is_oldest_first_and_capped(db_session):
    _, _, conversation = _conversation(db_session)
    for i in range(25):
        db_session.add(
            Message(
                conversation_id=conversation.id,
                business_id=conversation.business_id,
                direction="inbound",
                body=f"message {i}",
                status="received",
            )
        )
    db_session.commit()

    history = load_history(db_session, conversation.id)

    assert len(history) == 20
    assert history[0].body == "message 5"
    assert history[-1].body == "message 24"


def test_build_context_summary_is_none_for_a_short_conversation(db_session):
    _, _, conversation = _conversation(db_session)

    context = build_context(db_session, conversation, "hi there", llm=MockProvider())

    assert context.summary is None
