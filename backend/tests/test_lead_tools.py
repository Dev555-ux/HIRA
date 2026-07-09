"""Tests for app/ai/lead_tools.py: tool schemas' preview text and the execute
dispatcher — against the real app/services/leads.py (no external system to
fake, unlike the calendar tools) (DEC-033)."""

from datetime import datetime, timezone

from app.ai.llm.base import ToolCall
from app.ai.lead_tools import (
    CREATE_LEAD,
    SET_LEAD_FOLLOW_UP,
    UPDATE_LEAD_STAGE,
    execute_lead_tool_call,
    preview_lead_tool_call,
)
from app.models import Business, Customer, Lead, LeadEvent
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


# --- preview_lead_tool_call ---------------------------------------------------


def test_preview_create_lead_without_source():
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={})
    assert preview_lead_tool_call(tool_call) == "Log as a new lead"


def test_preview_create_lead_with_source():
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry"})
    preview = preview_lead_tool_call(tool_call)
    assert "new lead" in preview
    assert "WhatsApp inquiry" in preview


def test_preview_update_lead_stage():
    tool_call = ToolCall(id="1", name=UPDATE_LEAD_STAGE, arguments={"stage": "qualified"})
    assert preview_lead_tool_call(tool_call) == "Move lead to stage 'qualified'"


def test_preview_set_lead_follow_up():
    tool_call = ToolCall(
        id="1", name=SET_LEAD_FOLLOW_UP, arguments={"follow_up_at": "2026-08-10T09:00:00"}
    )
    assert "2026-08-10T09:00:00" in preview_lead_tool_call(tool_call)


def test_preview_unknown_lead_tool_falls_back_to_repr():
    tool_call = ToolCall(id="1", name="mystery_tool", arguments={"a": 1})
    assert "mystery_tool" in preview_lead_tool_call(tool_call)


# --- execute_lead_tool_call: create_lead --------------------------------------


def test_execute_create_lead_logs_a_new_lead(db_session):
    biz, customer = _business_customer(db_session)
    tool_call = ToolCall(
        id="1", name=CREATE_LEAD, arguments={"source": "WhatsApp inquiry", "notes": "Wants a quote"}
    )

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is True
    assert result.lead_id is not None
    lead = db_session.get(Lead, result.lead_id)
    assert lead.source == "WhatsApp inquiry"
    assert lead.notes == "Wants a quote"
    events = db_session.query(LeadEvent).filter(LeadEvent.lead_id == lead.id).all()
    assert any(e.type == "lead_created" for e in events)


def test_execute_create_lead_fails_gracefully_when_one_already_exists(db_session):
    biz, customer = _business_customer(db_session)
    existing = service_create_lead(db_session, biz.id, customer.id)
    tool_call = ToolCall(id="1", name=CREATE_LEAD, arguments={})

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is False
    assert "already exists" in result.message
    assert result.lead_id == existing.id


# --- execute_lead_tool_call: update_lead_stage --------------------------------


def test_execute_update_lead_stage_moves_the_pipeline_forward(db_session):
    biz, customer = _business_customer(db_session)
    lead = service_create_lead(db_session, biz.id, customer.id)
    tool_call = ToolCall(id="1", name=UPDATE_LEAD_STAGE, arguments={"stage": "qualified"})

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is True
    assert result.lead_id == lead.id
    db_session.refresh(lead)
    assert lead.stage == "qualified"
    events = db_session.query(LeadEvent).filter(LeadEvent.lead_id == lead.id).all()
    assert any(e.type == "stage_change" and e.to_value == "qualified" for e in events)


def test_execute_update_lead_stage_without_a_lead_fails_gracefully(db_session):
    biz, customer = _business_customer(db_session)
    tool_call = ToolCall(id="1", name=UPDATE_LEAD_STAGE, arguments={"stage": "qualified"})

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is False
    assert "No lead found" in result.message


def test_execute_update_lead_stage_rejects_an_invalid_stage(db_session):
    biz, customer = _business_customer(db_session)
    service_create_lead(db_session, biz.id, customer.id)
    tool_call = ToolCall(id="1", name=UPDATE_LEAD_STAGE, arguments={"stage": "not-a-real-stage"})

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is False
    assert "not a valid lead stage" in result.message


# --- execute_lead_tool_call: set_lead_follow_up -------------------------------


def test_execute_set_lead_follow_up_schedules_a_follow_up(db_session):
    biz, customer = _business_customer(db_session)
    lead = service_create_lead(db_session, biz.id, customer.id)
    tool_call = ToolCall(
        id="1", name=SET_LEAD_FOLLOW_UP, arguments={"follow_up_at": "2026-08-10T09:00:00+00:00"}
    )

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is True
    db_session.refresh(lead)
    assert lead.next_follow_up_at is not None


def test_execute_set_lead_follow_up_without_a_lead_fails_gracefully(db_session):
    biz, customer = _business_customer(db_session)
    tool_call = ToolCall(
        id="1", name=SET_LEAD_FOLLOW_UP, arguments={"follow_up_at": "2026-08-10T09:00:00"}
    )

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is False
    assert "No lead found" in result.message


def test_execute_set_lead_follow_up_with_bad_datetime_fails_gracefully(db_session):
    biz, customer = _business_customer(db_session)
    service_create_lead(db_session, biz.id, customer.id)
    tool_call = ToolCall(id="1", name=SET_LEAD_FOLLOW_UP, arguments={"follow_up_at": "not-a-date"})

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is False


def test_execute_unknown_lead_tool_fails_gracefully(db_session):
    biz, customer = _business_customer(db_session)
    tool_call = ToolCall(id="1", name="mystery_tool", arguments={})

    result = execute_lead_tool_call(db_session, biz.id, tool_call, customer_id=customer.id)

    assert result.success is False
    assert "Unknown tool" in result.message
