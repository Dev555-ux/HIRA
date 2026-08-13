"""Unit tests for app/ai/intent.py (Sprint 57) — pure, deterministic
classification logic, no LLM/DB/network involved."""

import pytest

from app.ai.intent import (
    ConversationCategory,
    classify_conversation,
    domains_for_action,
    tool_schemas_for_domain,
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


# Sprint 82 (production bug fix, DEC-058): "Can/could you <verb>" phrased
# politely around a concrete, singular instance ("a lead", "me", "this
# lead") is a real request, not a question about HIRA's abilities — the
# live-reproduced bug was exactly this: "Can you log me as a lead?" got
# classified CAPABILITY, no tool was offered, and the model fabricated a
# confirmation anyway. See app/ai/intent.py::_CONCRETE_REQUEST_RE.
@pytest.mark.parametrize(
    "text",
    [
        "Can you create a lead for me?",
        "Can you log me as a lead?",
        "Could you book an appointment tomorrow?",
        "Can you schedule a meeting?",
        "Could you update this lead?",
    ],
)
def test_a_polite_request_naming_a_concrete_instance_classifies_as_action(text):
    assert classify_conversation(text) == ConversationCategory.ACTION


# The inverse: the same verbs, but asking about the capability in general
# (a bare plural, no concrete instance) — these must NOT be swept into
# ACTION by the fix above.
@pytest.mark.parametrize(
    "text",
    [
        "Can you create leads?",
        "Can you schedule appointments?",
        "Can you update CRM records?",
    ],
)
def test_a_generic_capability_question_is_not_reclassified_as_action(text):
    assert classify_conversation(text) == ConversationCategory.CAPABILITY


@pytest.mark.parametrize(
    "text",
    [
        "Can you integrate with Salesforce?",
        "Are you able to send WhatsApp messages?",
    ],
)
def test_capability_style_questions_outside_the_known_verb_list_never_become_action(text):
    # Neither uses a recognized capability verb ("integrate", "are you able
    # to") — unaffected by this fix either way, but must never be swept into
    # ACTION (which would offer tools for a request that was never made).
    assert classify_conversation(text) != ConversationCategory.ACTION


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


def test_unknown_gibberish_input_returns_none_not_a_confident_guess():
    # Sprint 80: no rule matches at all -> None, distinct from a *confident*
    # CONVERSATION match (a real greeting/small-talk hit). A context-free
    # caller (tools_for_message) still coalesces this to CONVERSATION —
    # see test_tools_for_message_never_falls_back_to_all_tools below — but
    # classify_conversation itself must not silently discard the ambiguity,
    # since app/ai/plan.py needs it to decide whether to check for a
    # pending workflow.
    category = classify_conversation("zzxxqq flibbertigibbet asdkjh")
    assert category is None


def test_empty_input_falls_back_to_conversation():
    # Unlike gibberish, an empty message is unambiguous, not merely
    # unmatched — stays a confident CONVERSATION, never None.
    assert classify_conversation("") == ConversationCategory.CONVERSATION
    assert classify_conversation("   ") == ConversationCategory.CONVERSATION


def test_ambiguous_input_returns_none_or_a_valid_category_without_crashing():
    # Mixed signals (a knowledge-shaped question about scheduling) — the
    # point of this test isn't to pin one "correct" answer (there isn't a
    # single obviously correct one), it's to prove the classifier always
    # returns either a real category or the explicit "ambiguous" signal
    # (Sprint 80: None), never raises or guesses wildly.
    category = classify_conversation("What's the deal with scheduling around here?")
    assert category is None or isinstance(category, ConversationCategory)


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


# --- Sprint 75 (DEC-045): multi-domain detection ----------------------------


def test_domains_for_action_returns_a_single_domain_for_a_single_domain_message():
    """A single-domain message must produce the exact same single-item
    result tools_for_action's caller already relied on — acceptance
    criterion 9 (single-domain behaviour unchanged), at the domain-detection
    layer specifically."""
    assert domains_for_action("Book a meeting tomorrow") == ["calendar"]
    assert domains_for_action("I have a new lead for you") == ["crm"]


def test_domains_for_action_returns_no_domain_for_an_unrecognised_action():
    assert domains_for_action("Send an invoice.") == []


def test_domains_for_action_orders_by_first_mention_in_text():
    text = "Please reschedule my appointment to Thursday and log this as a new lead"
    # "reschedule" appears before "lead" in the text.
    assert domains_for_action(text) == ["calendar", "crm"]


def test_domains_for_action_orders_by_first_mention_reversed():
    text = "I have a lead who wants to book a meeting"
    # "lead" appears before "book" in the text.
    assert domains_for_action(text) == ["crm", "calendar"]


def test_domains_for_action_deduplicates_a_single_matching_category():
    # "book" and "schedule" both match the calendar category — must not
    # produce ["calendar", "calendar"].
    assert domains_for_action("Book and schedule my appointment") == ["calendar"]


def test_tool_schemas_for_domain_matches_the_stage_2_registry():
    assert {s.name for s in tool_schemas_for_domain("calendar")} == {
        BOOK_APPOINTMENT,
        CHECK_AVAILABILITY,
        RESCHEDULE_APPOINTMENT,
        CANCEL_APPOINTMENT,
    }
    assert {s.name for s in tool_schemas_for_domain("crm")} == {
        CREATE_LEAD,
        UPDATE_LEAD_STAGE,
        SET_LEAD_FOLLOW_UP,
    }


def test_tool_schemas_for_domain_returns_empty_for_an_unknown_domain():
    assert tool_schemas_for_domain("payments") == []
