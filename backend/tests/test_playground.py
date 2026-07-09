"""Tests for the AI Playground: reuses generate_reply(), never duplicates it."""

from app.ai.knowledge_base import index_entry
from app.ai.llm.mock import MockProvider
from app.ai.playground import (
    PLAYGROUND_PHONE,
    get_or_create_playground_conversation,
    playground_reply,
)
from app.models import Business, Conversation, Customer, Message
from tests.test_knowledge_base import FakeEmbeddingProvider


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

    response, retrieved, body = playground_reply(db_session, biz.id, "what are your hours?")

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


def test_playground_shows_a_preview_instead_of_a_blank_reply_for_a_proposed_tool_call(
    db_session, monkeypatch
):
    """Found during live verification (DEC-032): a real Groq call that
    proposed a booking returned response.text == "" — showing that directly
    in the playground would look like the AI silently failed."""
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

    response, _, body = playground_reply(db_session, biz.id, "book me tuesday at 2pm")

    assert response.text == ""
    assert "Cleaning" in body

    conversation = get_or_create_playground_conversation(db_session, biz.id)
    outbound = (
        db_session.query(Message)
        .filter_by(conversation_id=conversation.id, direction="outbound")
        .first()
    )
    assert outbound.type == "tool_call"
    assert outbound.body == body
