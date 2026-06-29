"""Tests for the orchestrator and background reply processing (mock providers)."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ai import processing
from app.ai.llm.mock import MockProvider
from app.ai.orchestrator import generate_reply
from app.models import Business, Conversation, Message
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
