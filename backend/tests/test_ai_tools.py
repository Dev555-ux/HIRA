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
    RESCHEDULE_APPOINTMENT,
    TOOL_SCHEMAS,
    confirmation_message_for,
    execute_check_availability,
    execute_tool_call,
    preview_tool_call,
    response_to_message_fields,
)
from app.calendar.providers.base import CalendarEventDraft, CalendarNotConnectedError
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.models import Business, Customer
from app.services.leads import create_lead as service_create_lead

NOW = datetime(2026, 8, 3, 9, 0, tzinfo=timezone.utc)


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


# --- response_to_message_fields --------------------------------------------


def test_response_to_message_fields_plain_text():
    response = LLMResponse(text="Sure, we're open 9-5", model="mock-1")

    type_, body, extra = response_to_message_fields(response)

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

    type_, body, extra = response_to_message_fields(response)

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

    type_, body, extra = response_to_message_fields(response)

    assert type_ == "text"
    assert body  # never blank
    assert extra == {}


def test_response_to_message_fields_prefers_real_text_over_the_fallback():
    tool_call = ToolCall(id="1", name=CHECK_AVAILABILITY, arguments={})
    response = LLMResponse(
        text="Let me look into that for you.", model="mock-1", tool_calls=[tool_call]
    )

    type_, body, extra = response_to_message_fields(response)

    assert type_ == "text"
    assert body == "Let me look into that for you."
    assert extra == {}


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
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is True
    assert result.appointment_id == appointment.id


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
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is False
    assert "No upcoming appointment" in result.message


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
        db_session, biz.id, tool_call, customer_id=customer.id, conversation_id=None
    )

    assert result.success is True
    assert result.appointment_id == appointment.id


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

    type_, body, extra = response_to_message_fields(response)

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
