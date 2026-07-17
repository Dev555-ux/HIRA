"""Tests for app/ai/prompts.py::build_system_prompt against a directly
constructed ConversationContext (DEC-034) — a pure unit test of the
formatting logic, independent of the Context Builder's assembly."""

from datetime import datetime, timezone

from app.ai.context import ConversationContext
from app.ai.prompts import build_demo_system_prompt, build_system_prompt
from app.models import Business, Customer, Lead, Message


def _business(**kwargs):
    defaults = dict(name="Clinic A", timezone="UTC", working_hours=None)
    defaults.update(kwargs)
    return Business(**defaults)


def _customer(**kwargs):
    defaults = dict(business_id=None, wa_phone="+15551230000", display_name=None)
    defaults.update(kwargs)
    return Customer(**defaults)


def _context(**overrides):
    defaults = dict(
        business=_business(),
        customer=_customer(),
        lead=None,
        upcoming_appointments=[],
        retrieved_kb=[],
        has_knowledge=True,
        summary=None,
        history=[],
    )
    defaults.update(overrides)
    return ConversationContext(**defaults)


def test_no_knowledge_base_entries_shows_the_fallback_note():
    prompt = build_system_prompt(_context())

    assert "No relevant knowledge base entries" in prompt


def test_scheduling_context_included_when_business_has_working_hours():
    business = _business(working_hours={"mon": {"open": "09:00", "close": "17:00"}, "tue": None})

    prompt = build_system_prompt(_context(business=business))

    assert "Working hours" in prompt
    assert "mon: 09:00-17:00" in prompt
    assert "tue: closed" in prompt


def test_falls_back_to_utc_for_unknown_timezone():
    # Regression: a business with an invalid/legacy `timezone` value (e.g.
    # "asia" instead of "Asia/Kolkata") must not crash reply generation —
    # every AI reply builds this prompt, so one bad value would 500 the
    # whole conversation instead of just degrading to UTC.
    business = _business(timezone="asia")

    prompt = build_system_prompt(_context(business=business))

    assert "(asia)" in prompt


def test_customer_name_included_when_known():
    customer = _customer(display_name="Alex Rivera")

    prompt = build_system_prompt(_context(customer=customer))

    assert "\nCustomer context:\n" in prompt
    assert "Alex Rivera" in prompt


def test_no_customer_context_section_when_nothing_to_show():
    prompt = build_system_prompt(_context())

    assert "\nCustomer context:\n" not in prompt


def test_lead_details_included_when_present():
    lead = Lead(
        business_id=None,
        customer_id=None,
        stage="qualified",
        source="WhatsApp inquiry",
        notes="Wants a quote",
    )

    prompt = build_system_prompt(_context(lead=lead))

    assert "stage: qualified" in prompt
    assert "source: WhatsApp inquiry" in prompt
    assert "notes: Wants a quote" in prompt


def test_upcoming_appointment_included_when_present():
    class _FakeAppointment:
        starts_at = datetime(2026, 8, 5, 14, 0, tzinfo=timezone.utc)
        ends_at = datetime(2026, 8, 5, 15, 0, tzinfo=timezone.utc)

    prompt = build_system_prompt(_context(upcoming_appointments=[_FakeAppointment()]))

    assert "Upcoming appointment" in prompt
    assert "2026-08-05T14:00:00" in prompt


def test_conversation_summary_included_when_present():
    prompt = build_system_prompt(_context(summary="Customer asked about pricing."))

    assert "Conversation so far (summary of earlier messages)" in prompt
    assert "Customer asked about pricing." in prompt


def test_no_summary_section_when_none():
    prompt = build_system_prompt(_context(summary=None))

    assert "Conversation so far (summary of earlier messages)" not in prompt


def test_availability_note_still_appended_when_given():
    prompt = build_system_prompt(_context(), availability_note="(Available slots: none)")

    assert "Availability check result" in prompt
    assert "(Available slots: none)" in prompt


def test_demo_prompt_does_not_include_kb_grounding_language():
    # Sprint 55: Demo Mode is a genuinely separate prompt, not a variant of
    # the grounded one — it must never tell the model to answer "ONLY using
    # the knowledge base below" when there is no knowledge base yet.
    prompt = build_demo_system_prompt(_context())

    assert "Answer ONLY using the information" not in prompt
    assert "Knowledge base:" not in prompt


def test_demo_prompt_explains_capabilities():
    prompt = build_demo_system_prompt(_context())

    assert "schedul" in prompt.lower() or "book" in prompt.lower()
    assert "lead" in prompt.lower()
    assert "remember" in prompt.lower()


def test_demo_prompt_includes_business_name_when_known():
    business = _business(name="Bright Smile Dental")

    prompt = build_demo_system_prompt(_context(business=business))

    assert "Bright Smile Dental" in prompt


def test_demo_prompt_includes_suggestions_hint_on_first_turn():
    # history with no outbound message yet == no assistant reply has been
    # sent in this conversation == this response will be the first one.
    context = _context(history=[])

    prompt = build_demo_system_prompt(context)

    assert "first message" in prompt.lower()


def test_demo_prompt_omits_suggestions_hint_after_the_first_turn():
    history = [
        Message(
            conversation_id=None,
            business_id=None,
            direction="inbound",
            body="hi",
            type="text",
            status="received",
        ),
        Message(
            conversation_id=None,
            business_id=None,
            direction="outbound",
            body="Hello! I'm HIRA.",
            type="text",
            status="sent",
        ),
    ]

    prompt = build_demo_system_prompt(_context(history=history))

    assert "first message" not in prompt.lower()
