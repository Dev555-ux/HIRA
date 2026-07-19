"""Unit tests for app/ai/intent.py (Sprint 57) — pure, deterministic
classification logic, no LLM/DB/network involved."""

import pytest

from app.ai.intent import (
    ConversationCategory,
    classify_conversation,
    tools_for_action,
    tools_for_message,
)
from app.ai.lead_tools import CREATE_LEAD, SET_LEAD_FOLLOW_UP, UPDATE_LEAD_STAGE
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    RESCHEDULE_APPOINTMENT,
)


@pytest.mark.parametrize(
    "text",
    ["Hi", "Hello", "Hey", "How are you?", "Tell me about yourself."],
)
def test_classifies_conversation(text):
    assert classify_conversation(text) == ConversationCategory.CONVERSATION


@pytest.mark.parametrize(
    "text",
    [
        "Can you schedule meetings?",
        "Can you create CRM leads?",
        "Can you answer customers?",
        "Can you remember conversations?",
        "Can you learn my business?",
        "What can you do?",
    ],
)
def test_classifies_capability(text):
    assert classify_conversation(text) == ConversationCategory.CAPABILITY


@pytest.mark.parametrize(
    "text",
    [
        "What are your opening hours?",
        "What are your business hours?",
        "What services do you offer?",
        "What is your refund policy?",
        "What products do you sell?",
    ],
)
def test_classifies_knowledge(text):
    assert classify_conversation(text) == ConversationCategory.KNOWLEDGE


@pytest.mark.parametrize(
    "text",
    [
        "Book a meeting tomorrow.",
        "Schedule next Tuesday.",
        "Cancel my appointment.",
        "Can I book tuesday morning?",
    ],
)
def test_classifies_calendar_action(text):
    assert classify_conversation(text) == ConversationCategory.ACTION
    names = {schema.name for schema in tools_for_action(text)}
    assert names == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }


@pytest.mark.parametrize("text", ["Create a lead for John.", "Add John as a lead."])
def test_classifies_crm_action(text):
    assert classify_conversation(text) == ConversationCategory.ACTION
    names = {schema.name for schema in tools_for_action(text)}
    assert names == {CREATE_LEAD, UPDATE_LEAD_STAGE, SET_LEAD_FOLLOW_UP}


def test_unknown_gibberish_input_falls_back_to_conversation():
    category = classify_conversation("zzxxqq flibbertigibbet asdkjh")
    assert category == ConversationCategory.CONVERSATION


def test_empty_input_falls_back_to_conversation():
    assert classify_conversation("") == ConversationCategory.CONVERSATION
    assert classify_conversation("   ") == ConversationCategory.CONVERSATION


def test_ambiguous_input_returns_a_valid_category_without_crashing():
    # Mixed signals (a knowledge-shaped question about scheduling) — the
    # point of this test isn't to pin one "correct" answer (there isn't a
    # single obviously correct one), it's to prove the classifier always
    # returns *some* valid category rather than raising or guessing wildly.
    category = classify_conversation("What's the deal with scheduling around here?")
    assert isinstance(category, ConversationCategory)


def test_action_classified_but_unrecognised_tool_category_yields_no_tools():
    # "Send an invoice" is unambiguously an action, but there is no Payments
    # category yet (only Calendar and CRM are implemented this sprint).
    # tools_for_action must degrade to [] rather than guessing a category —
    # this is the low-confidence-fallback path, exercised end-to-end via
    # tools_for_message below.
    assert classify_conversation("Send an invoice.") == ConversationCategory.ACTION
    assert tools_for_action("Send an invoice.") == []


def test_tools_for_message_never_falls_back_to_all_tools():
    # The old architecture's failure mode was "when in doubt, send every
    # tool." This asserts that structurally can't happen anymore: every
    # non-Action category yields [], and an Action with no recognised
    # category also yields [] — never the full TOOL_SCHEMAS list.
    for text in [
        "asdkjasdkj",
        "Hi",
        "What can you do?",
        "What are your hours?",
        "Send an invoice.",
    ]:
        _, tools = tools_for_message(text)
        assert tools == []


def test_tools_for_message_returns_category_and_tools_together():
    category, tools = tools_for_message("Book a meeting tomorrow")
    assert category == ConversationCategory.ACTION
    assert {schema.name for schema in tools} == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }
