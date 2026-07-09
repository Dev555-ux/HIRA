"""Tests for app/ai/memory.py: conversation-summary regeneration/watermark
logic (DEC-034), against a MockProvider (no real LLM calls)."""

from app.ai.llm.mock import MockProvider
from app.ai.memory import HISTORY_LIMIT, get_conversation_summary
from app.models import Business, Conversation, Customer, Message


def _conversation_with_messages(db, count: int) -> Conversation:
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db.add(conversation)
    db.flush()
    for i in range(count):
        db.add(
            Message(
                conversation_id=conversation.id,
                business_id=biz.id,
                direction="inbound" if i % 2 == 0 else "outbound",
                body=f"message {i}",
                status="sent" if i % 2 else "received",
            )
        )
    db.commit()
    db.refresh(conversation)
    return conversation


def test_returns_none_when_conversation_has_not_exceeded_the_window(db_session):
    conversation = _conversation_with_messages(db_session, HISTORY_LIMIT)

    summary = get_conversation_summary(db_session, conversation, llm=MockProvider())

    assert summary is None


def test_regenerates_summary_once_the_window_is_exceeded(db_session):
    conversation = _conversation_with_messages(db_session, HISTORY_LIMIT + 5)
    llm = MockProvider(fixed_reply="Customer asked about pricing; no decision yet.")

    summary = get_conversation_summary(db_session, conversation, llm=llm)

    assert summary == "Customer asked about pricing; no decision yet."
    db_session.refresh(conversation)
    assert conversation.summary == summary
    assert conversation.summary_message_count == 5


def test_does_not_regenerate_when_watermark_is_already_current(db_session):
    conversation = _conversation_with_messages(db_session, HISTORY_LIMIT + 5)
    conversation.summary = "Existing summary"
    conversation.summary_message_count = 5
    db_session.commit()

    def _explode(*args, **kwargs):
        raise AssertionError("should not call the LLM when the watermark is current")

    llm = MockProvider()
    llm.generate = _explode

    summary = get_conversation_summary(db_session, conversation, llm=llm)

    assert summary == "Existing summary"


def test_regenerates_when_the_window_has_advanced_past_the_watermark(db_session):
    conversation = _conversation_with_messages(db_session, HISTORY_LIMIT + 10)
    conversation.summary = "Stale summary"
    conversation.summary_message_count = 5  # only covers the first 5 of the 10 "older" messages
    db_session.commit()
    llm = MockProvider(fixed_reply="Fresh summary covering all 10 older messages.")

    summary = get_conversation_summary(db_session, conversation, llm=llm)

    assert summary == "Fresh summary covering all 10 older messages."
    db_session.refresh(conversation)
    assert conversation.summary_message_count == 10


def test_falls_back_to_existing_summary_when_llm_call_fails(db_session):
    conversation = _conversation_with_messages(db_session, HISTORY_LIMIT + 5)
    conversation.summary = "Old summary"
    conversation.summary_message_count = 2  # stale, would normally trigger regeneration
    db_session.commit()

    from app.ai.llm.base import LLMError

    class _FailingProvider(MockProvider):
        def generate(self, **kwargs):
            raise LLMError("rate limited")

    summary = get_conversation_summary(db_session, conversation, llm=_FailingProvider())

    assert summary == "Old summary"
    db_session.refresh(conversation)
    assert conversation.summary == "Old summary"
    assert conversation.summary_message_count == 2  # watermark untouched on failure


def test_uses_default_provider_when_none_injected(db_session, monkeypatch):
    conversation = _conversation_with_messages(db_session, HISTORY_LIMIT + 1)
    monkeypatch.setattr(
        "app.ai.memory.get_llm_provider",
        lambda: MockProvider(fixed_reply="Default provider summary."),
    )

    summary = get_conversation_summary(db_session, conversation)

    assert summary == "Default provider summary."
