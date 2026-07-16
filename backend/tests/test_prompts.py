"""Tests for app/ai/prompts.py::build_system_prompt against a directly
constructed ConversationContext (DEC-034) — a pure unit test of the
formatting logic, independent of the Context Builder's assembly."""

from datetime import datetime, timezone

from app.ai.context import ConversationContext
from app.ai.prompts import build_system_prompt
from app.models import Business, Customer, Lead


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
