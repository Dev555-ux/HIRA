"""Tests for app/ai/tools.py: tool schemas' preview text, response->message
field mapping, and the execute dispatcher — against a Mock-backed
AppointmentService (the real factory is monkeypatched out) (DEC-032)."""

from datetime import datetime, timedelta, timezone

from app.ai.lead_tools import CREATE_LEAD, UPDATE_LEAD_STAGE
from app.ai.llm.base import LLMResponse, ToolCall
from app.ai.tool_results import ToolExecutionResult
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    READ_TOOL_EXECUTORS,
    READ_TOOL_NAMES,
    RESCHEDULE_APPOINTMENT,
    TOOL_SCHEMAS,
    confirmation_message_for,
    execute_check_availability,
    execute_tool_call,
    failure_message_for,
    preview_tool_call,
    response_to_message_fields,
)
from app.calendar.providers.base import (
    CalendarAlreadyCancelledError,
    CalendarConflictError,
    CalendarEventDraft,
    CalendarNotConnectedError,
    CalendarValidationError,
)
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.models import Business, Customer
from app.services.leads import create_lead as service_create_lead

NOW = datetime.now(timezone.utc)


def _business_customer(db):
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    return biz, customer


def _mock_appointment_service(db, business_id, *, provider=None) -> AppointmentService:
    return AppointmentService(
        db, business_id, provider or MockCalendarProvider(), calendar_id="primary"
    )


# --- preview_tool_call ---------------------------------------------------


def test_preview_book_appointment():
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Dental cleaning",
        },
    )
    assert "Dental cleaning" in preview_tool_call(tool_call)


def test_preview_reschedule_appointment():
    tool_call = ToolCall(
        id="1",
        name=RESCHEDULE_APPOINTMENT,
        arguments={"starts_at": "2026-08-05T14:00:00", "ends_at": "2026-08-05T15:00:00"},
    )
    assert "Reschedule" in preview_tool_call(tool_call)


def test_preview_cancel_appointment():
    tool_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})
    assert preview_tool_call(tool_call) == "Cancel your upcoming appointment"


def test_preview_unknown_tool_falls_back_to_repr():
    tool_call = ToolCall(id="1", name="mystery_tool", arguments={"a": 1})
    assert "mystery_tool" in preview_tool_call(tool_call)


# --- confirmation_message_for (Section A1 fix — Autonomous Mode only) ------


def test_confirmation_book_appointment_differs_from_preview():
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-05T14:00:00",
            "ends_at": "2026-08-05T15:00:00",
            "summary": "Dental cleaning",
        },
    )
    result = ToolExecutionResult(True, "Appointment booked.")

    confirmation = confirmation_message_for(tool_call, result)

    assert confirmation == (
        "You're all set! Dental cleaning is booked for 2026-08-05T14:00:00 to 2026-08-05T15:00:00."
    )
    assert confirmation != preview_tool_call(tool_call)


def test_confirmation_reschedule_appointment_differs_from_preview():
    tool_call = ToolCall(
        id="1",
        name=RESCHEDULE_APPOINTMENT,
        arguments={"starts_at": "2026-08-05T14:00:00", "ends_at": "2026-08-05T15:00:00"},
    )
    result = ToolExecutionResult(True, "Appointment rescheduled.")

    confirmation = confirmation_message_for(tool_call, result)

    assert confirmation == (
        "Your appointment has been rescheduled to 2026-08-05T14:00:00 – 2026-08-05T15:00:00."
    )
    assert confirmation != preview_tool_call(tool_call)


def test_confirmation_cancel_appointment_differs_from_preview():
    tool_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})
    result = ToolExecutionResult(True, "Appointment cancelled.")

    confirmation = confirmation_message_for(tool_call, result)

    assert confirmation == "Your appointment has been cancelled."
    assert confirmation != preview_tool_call(tool_call)  # "Cancel your upcoming appointment"


def test_confirmation_lead_tool_differs_from_preview():
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    result = ToolExecutionResult(True, "Lead logged.")

    confirmation = confirmation_message_for(tool_call, result)

    assert confirmation == "Thanks — that's been taken care of."
    assert confirmation != preview_tool_call(tool_call)  # "Log as a new lead (source: ...)"


# --- failure_message_for (Sprint 83 production bug fix, DEC-059) -----------
# The live-reproduced bug: a customer heard raw internal strings like
# "Requested slot overlaps an existing appointment" verbatim. This is the
# failure-path counterpart to confirmation_message_for above — every case
# here must never equal the internal result.message it was built from.


def test_failure_message_for_conflict():
    result = ToolExecutionResult(False, "Requested slot overlaps an existing appointment", reason="conflict")

    message = failure_message_for(result)

    assert message == (
        "That time isn't available because it overlaps another appointment. "
        "Would you like to choose another time?"
    )
    assert message != result.message


def test_failure_message_for_needs_confirmation():
    result = ToolExecutionResult(
        False,
        "This action needs to be confirmed with the customer before it can be completed.",
        reason="needs_confirmation",
    )

    message = failure_message_for(result)

    assert message == (
        "I need your confirmation before making that change. Would you like me to proceed?"
    )
    assert message != result.message


def test_failure_message_for_not_found():
    result = ToolExecutionResult(False, "No upcoming appointment found to modify.", reason="not_found")

    message = failure_message_for(result)

    assert message == (
        "I couldn't find an upcoming appointment to change. Can you tell me which appointment you mean?"
    )
    assert message != result.message


def test_failure_message_for_already_cancelled():
    result = ToolExecutionResult(
        False,
        "This appointment has already been cancelled and can't be rescheduled",
        reason="already_cancelled",
    )

    message = failure_message_for(result)

    assert message == (
        "That appointment has already been cancelled. Would you like to book a new one instead?"
    )
    assert message != result.message


def test_failure_message_for_invalid_request():
    result = ToolExecutionResult(
        False, "Cannot book an appointment in the past.", reason="invalid_request"
    )

    message = failure_message_for(result)

    assert message == "That time doesn't work — could you try a different date or time?"
    assert message != result.message


def test_failure_message_for_falls_back_to_raw_message_when_reason_is_unmapped():
    """A CRM failure (or any future CalendarError this fix doesn't cover
    yet) has no reason, or a reason with no phrasing — unchanged, existing
    behavior, not something this fix touches."""
    result = ToolExecutionResult(False, "A lead already exists for this customer.")

    assert failure_message_for(result) == result.message


def test_execute_tool_call_tags_a_validation_failure_and_writes_nothing(db_session, monkeypatch):
    """End-to-end through execute_tool_call (not just the CalendarError ->
    reason mapping in isolation): a past-dated booking request is rejected
    by AppointmentService, and the resulting ToolExecutionResult carries the
    reason failure_message_for needs — not left for the caller to guess at
    from result.message's text."""
    from app.models import Appointment

    biz, customer = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    past = NOW - timedelta(days=5)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": past.isoformat(),
            "ends_at": (past + timedelta(minutes=30)).isoformat(),
            "summary": "Should be rejected",
        },
    )

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False
    assert result.reason == "invalid_request"
    assert failure_message_for(result) == (
        "That time doesn't work — could you try a different date or time?"
    )
    from sqlalchemy import select

    assert db_session.scalars(select(Appointment)).all() == []


def test_execute_reschedule_of_an_already_cancelled_appointment_reports_not_found(
    db_session, monkeypatch
):
    """execute_tool_call's reschedule/cancel dispatch resolves "which
    appointment" via get_upcoming_appointments() (DEC-034), which already
    excludes cancelled ones — so from the AI/WhatsApp path, a cancelled
    appointment looks identical to having no upcoming appointment at all,
    never reaching AppointmentService.reschedule_appointment()'s own
    CalendarAlreadyCancelledError check. That check exists for the direct
    REST path instead (app/api/appointments.py, tested in
    tests/test_appointment_service.py::test_reschedule_rejects_an_already_cancelled_appointment
    and tests/test_appointments_api.py) — this test documents that this
    dispatcher is naturally protected already, by construction, not by
    the new check."""
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    service.cancel_appointment(appointment_id=appointment.id)
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    new_starts_at = starts_at + timedelta(hours=3)
    new_ends_at = new_starts_at + timedelta(minutes=30)
    tool_call = ToolCall(
        id="1",
        name=RESCHEDULE_APPOINTMENT,
        arguments={"starts_at": new_starts_at.isoformat(), "ends_at": new_ends_at.isoformat()},
    )

    result = execute_tool_call(
        db_session,
        biz.id,
        tool_call,
        customer_id=customer.id,
        conversation_id=None,
        human_approved=True,
    )

    assert result.success is False
    assert result.reason == "not_found"
    db_session.refresh(appointment)
    assert appointment.status == "cancelled"  # untouched


# --- response_to_message_fields --------------------------------------------


def test_response_to_message_fields_plain_text():
    response = LLMResponse(text="Sure, we're open 9-5", model="mock-1")

    fields = response_to_message_fields(response)

    assert len(fields) == 1
    type_, body, extra = fields[0]
    assert type_ == "text"
    assert body == "Sure, we're open 9-5"
    assert extra == {}


def test_response_to_message_fields_tool_call():
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={"starts_at": "x", "ends_at": "y", "summary": "Cleaning"},
    )
    response = LLMResponse(text="", model="mock-1", tool_calls=[tool_call])

    fields = response_to_message_fields(response)

    assert len(fields) == 1
    type_, body, extra = fields[0]
    assert type_ == "tool_call"
    assert "Cleaning" in body
    assert extra == {"tool_name": BOOK_APPOINTMENT, "tool_arguments": tool_call.arguments}


def test_response_to_message_fields_falls_back_to_text_for_a_stray_check_availability_call():
    """Found live: a real Groq call proposed check_availability a second time
    (after generate_reply()'s one bounded round-trip already ran) — approving
    that as a "tool_call" pending item would be meaningless (execute_tool_call
    has no dispatch case for it), so this must fall back to plain text."""
    tool_call = ToolCall(
        id="1",
        name=CHECK_AVAILABILITY,
        arguments={"starts_at": "2026-08-05T09:00:00", "ends_at": "2026-08-05T17:00:00"},
    )
    response = LLMResponse(text="", model="mock-1", tool_calls=[tool_call])

    fields = response_to_message_fields(response)

    assert len(fields) == 1
    type_, body, extra = fields[0]
    assert type_ == "text"
    assert body  # never blank
    assert extra == {}


def test_response_to_message_fields_prefers_real_text_over_the_fallback():
    tool_call = ToolCall(id="1", name=CHECK_AVAILABILITY, arguments={})
    response = LLMResponse(
        text="Let me look into that for you.", model="mock-1", tool_calls=[tool_call]
    )

    fields = response_to_message_fields(response)

    assert len(fields) == 1
    type_, body, extra = fields[0]
    assert type_ == "text"
    assert body == "Let me look into that for you."
    assert extra == {}


# --- response_to_message_fields: Sprint 74 Phase 1 (DEC-043) two-call cap ---


def test_response_to_message_fields_returns_up_to_two_tool_calls():
    first = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={"starts_at": "x", "ends_at": "y", "summary": "Cleaning"},
    )
    second = ToolCall(id="2", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    response = LLMResponse(text="", model="mock-1", tool_calls=[first, second])

    fields = response_to_message_fields(response)

    assert len(fields) == 2
    assert fields[0][0] == "tool_call"
    assert fields[0][2] == {"tool_name": BOOK_APPOINTMENT, "tool_arguments": first.arguments}
    assert fields[1][0] == "tool_call"
    assert fields[1][2] == {"tool_name": CREATE_LEAD, "tool_arguments": second.arguments}


def test_response_to_message_fields_caps_at_two_even_if_model_proposes_more():
    calls = [
        ToolCall(id="1", name=BOOK_APPOINTMENT, arguments={}),
        ToolCall(id="2", name=CREATE_LEAD, arguments={}),
        ToolCall(id="3", name=UPDATE_LEAD_STAGE, arguments={}),
    ]
    response = LLMResponse(text="", model="mock-1", tool_calls=calls)

    fields = response_to_message_fields(response)

    assert len(fields) == 2
    assert [f[2]["tool_name"] for f in fields] == [BOOK_APPOINTMENT, CREATE_LEAD]


def test_response_to_message_fields_skips_a_leading_stray_check_availability_and_keeps_the_real_call():
    """A stray check_availability contributes no entry of its own (existing
    behaviour, unchanged), but no longer swallows a real second call
    alongside it — Sprint 74's one behavioural change to this fallback."""
    stray_check = ToolCall(id="1", name=CHECK_AVAILABILITY, arguments={})
    real_call = ToolCall(id="2", name=BOOK_APPOINTMENT, arguments={"summary": "Cleaning"})
    response = LLMResponse(text="", model="mock-1", tool_calls=[stray_check, real_call])

    fields = response_to_message_fields(response)

    assert len(fields) == 1
    assert fields[0][0] == "tool_call"
    assert fields[0][2]["tool_name"] == BOOK_APPOINTMENT


# --- execute_tool_call -------------------------------------------------------


def test_execute_book_appointment_creates_appointment(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "summary": "Dental cleaning",
        },
    )

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is True
    assert result.appointment_id is not None


def test_execute_book_appointment_reports_conflict(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    busy_provider = MockCalendarProvider()
    busy_provider.create_event(
        calendar_id="primary",
        draft=CalendarEventDraft(starts_at=starts_at, ends_at=ends_at, summary="Existing"),
    )
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id, provider=busy_provider),
    )
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "summary": "Double booked",
        },
    )

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False
    # Sprint 83 (DEC-059): tagged so failure_message_for can translate this
    # into natural customer-facing text instead of result.message's raw
    # "Requested slot overlaps an existing appointment".
    assert result.reason == "conflict"


def test_execute_reschedule_finds_upcoming_appointment(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    new_starts_at = starts_at + timedelta(hours=3)
    new_ends_at = new_starts_at + timedelta(minutes=30)
    tool_call = ToolCall(
        id="1",
        name=RESCHEDULE_APPOINTMENT,
        arguments={"starts_at": new_starts_at.isoformat(), "ends_at": new_ends_at.isoformat()},
    )

    result = execute_tool_call(
        db_session,
        biz.id,
        tool_call,
        customer_id=customer.id,
        conversation_id=None,
        human_approved=True,
    )

    assert result.success is True
    assert result.appointment_id == appointment.id


def test_execute_reschedule_without_confirmation_is_refused(db_session, monkeypatch):
    """Critical audit fix: reschedule is governance-gated (REQUIRES_CONFIRMATION)
    — executing it with neither human_approved nor a matching pending_action
    must be refused before it ever reaches the calendar provider."""
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    new_starts_at = starts_at + timedelta(hours=3)
    new_ends_at = new_starts_at + timedelta(minutes=30)
    tool_call = ToolCall(
        id="1",
        name=RESCHEDULE_APPOINTMENT,
        arguments={"starts_at": new_starts_at.isoformat(), "ends_at": new_ends_at.isoformat()},
    )

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False
    assert "confirm" in result.message.lower()
    assert result.reason == "needs_confirmation"


def test_execute_reschedule_without_upcoming_appointment_fails_gracefully(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    tool_call = ToolCall(
        id="1",
        name=RESCHEDULE_APPOINTMENT,
        arguments={
            "starts_at": NOW.isoformat(),
            "ends_at": (NOW + timedelta(hours=1)).isoformat(),
        },
    )

    result = execute_tool_call(
        db_session,
        biz.id,
        tool_call,
        customer_id=customer.id,
        conversation_id=None,
        human_approved=True,
    )

    assert result.success is False
    assert "No upcoming appointment" in result.message
    assert result.reason == "not_found"


def test_execute_cancel_appointment(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    tool_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})

    result = execute_tool_call(
        db_session,
        biz.id,
        tool_call,
        customer_id=customer.id,
        conversation_id=None,
        human_approved=True,
    )

    assert result.success is True
    assert result.appointment_id == appointment.id


def test_execute_cancel_without_confirmation_is_refused(db_session, monkeypatch):
    """Critical audit fix: same as reschedule above — cancel_appointment is
    REQUIRES_CONFIRMATION and must never execute without proof of it, even
    when there *is* a real upcoming appointment to cancel."""
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    tool_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False
    assert "confirm" in result.message.lower()
    # The refusal happened before any write — the appointment is untouched.
    db_session.refresh(appointment)
    assert appointment.status == "booked"


def test_execute_cancel_with_matching_pending_action_succeeds(db_session, monkeypatch):
    """The AI-mediated confirmation path (DEC-051): a matching pending_action
    from a prior turn satisfies governance without a human in the loop."""
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    appointment = service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    tool_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})

    result = execute_tool_call(
        db_session,
        biz.id,
        tool_call,
        customer_id=customer.id,
        conversation_id=None,
        pending_action="calendar_cancel",
    )

    assert result.success is True
    assert result.appointment_id == appointment.id


def test_execute_cancel_with_mismatched_pending_action_is_refused(db_session, monkeypatch):
    """A pending_action for a *different* action (e.g. the customer confirmed
    a reschedule, not a cancel) must not authorize cancel_appointment."""
    biz, customer = _business_customer(db_session)
    service = _mock_appointment_service(db_session, biz.id)
    starts_at = NOW + timedelta(hours=2)
    ends_at = starts_at + timedelta(minutes=30)
    service.book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=ends_at,
        summary="Dental cleaning",
    )
    monkeypatch.setattr("app.ai.tools.get_appointment_service", lambda db, business_id: service)
    tool_call = ToolCall(id="1", name=CANCEL_APPOINTMENT, arguments={})

    result = execute_tool_call(
        db_session,
        biz.id,
        tool_call,
        customer_id=customer.id,
        conversation_id=None,
        pending_action="calendar_reschedule",
    )

    assert result.success is False
    assert "confirm" in result.message.lower()


def test_execute_tool_call_with_bad_arguments_fails_gracefully(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    tool_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={"starts_at": "not-a-date", "ends_at": "also-not-a-date", "summary": "x"},
    )

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False


def test_execute_unknown_tool_fails_gracefully(db_session, monkeypatch):
    biz, customer = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    tool_call = ToolCall(id="1", name="mystery_tool", arguments={})

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False
    assert "Unknown tool" in result.message


# --- DEC-050: generic read/write tool registries ----------------------------


def test_read_tool_names_contains_only_check_availability():
    # Today's only read-only tool — a future domain's own lookup tool joins
    # this set purely by marking its ToolSchema interaction_type="read",
    # no other code changes required.
    assert READ_TOOL_NAMES == {CHECK_AVAILABILITY}


def test_every_write_tool_schema_defaults_to_write_interaction_type():
    write_tools = {BOOK_APPOINTMENT, CANCEL_APPOINTMENT, RESCHEDULE_APPOINTMENT, CREATE_LEAD}
    for schema in TOOL_SCHEMAS:
        if schema.name in write_tools:
            assert schema.interaction_type == "write"


def test_read_tool_executors_covers_every_read_tool_with_a_matching_signature():
    assert set(READ_TOOL_EXECUTORS) == READ_TOOL_NAMES
    assert READ_TOOL_EXECUTORS[CHECK_AVAILABILITY] is execute_check_availability


# --- execute_check_availability ----------------------------------------------


def test_execute_check_availability_returns_slots(db_session, monkeypatch):
    biz, _ = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    tool_call = ToolCall(
        id="1",
        name=CHECK_AVAILABILITY,
        arguments={"starts_at": NOW.isoformat(), "ends_at": (NOW + timedelta(hours=1)).isoformat()},
    )

    note = execute_check_availability(db_session, biz.id, tool_call)

    assert "Available slots" in note


def test_execute_check_availability_reports_calendar_errors(db_session, monkeypatch):
    biz, _ = _business_customer(db_session)

    def _raise(db, business_id):
        raise CalendarNotConnectedError("not connected")

    monkeypatch.setattr("app.ai.tools.get_appointment_service", _raise)
    tool_call = ToolCall(
        id="1",
        name=CHECK_AVAILABILITY,
        arguments={"starts_at": NOW.isoformat(), "ends_at": (NOW + timedelta(hours=1)).isoformat()},
    )

    note = execute_check_availability(db_session, biz.id, tool_call)

    assert "Calendar unavailable" in note


def test_tool_schemas_include_both_calendar_and_lead_tools():
    names = {schema.name for schema in TOOL_SCHEMAS}
    assert {
        BOOK_APPOINTMENT,
        CANCEL_APPOINTMENT,
        RESCHEDULE_APPOINTMENT,
        CHECK_AVAILABILITY,
    }.issubset(names)
    assert {CREATE_LEAD, UPDATE_LEAD_STAGE}.issubset(names)


def test_execute_tool_call_dispatches_lead_tools_to_the_crm_path(db_session):
    biz, customer = _business_customer(db_session)
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is True
    assert result.lead_id is not None


def test_execute_tool_call_dispatches_update_lead_stage_to_the_crm_path(db_session):
    biz, customer = _business_customer(db_session)
    lead = service_create_lead(db_session, biz.id, customer.id)
    tool_call = ToolCall(id="1", name=UPDATE_LEAD_STAGE, arguments={"stage": "won"})

    result = execute_tool_call(
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is True
    assert result.lead_id == lead.id


def test_response_to_message_fields_tool_call_for_a_lead_tool():
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    response = LLMResponse(text="", model="mock-1", tool_calls=[tool_call])

    type_, body, extra = response_to_message_fields(response)[0]

    assert type_ == "tool_call"
    assert "new lead" in body
    assert extra == {"tool_name": CREATE_LEAD, "tool_arguments": tool_call.arguments}


def test_execute_check_availability_with_bad_arguments(db_session, monkeypatch):
    biz, _ = _business_customer(db_session)
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: _mock_appointment_service(db, business_id),
    )
    tool_call = ToolCall(
        id="1", name=CHECK_AVAILABILITY, arguments={"starts_at": "not-a-date", "ends_at": "nope"}
    )

    note = execute_check_availability(db_session, biz.id, tool_call)

    assert "Could not understand" in note
