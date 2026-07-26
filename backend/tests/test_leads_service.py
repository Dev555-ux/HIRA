"""Unit tests for app/services/leads.py: create/update/delete, LeadEvent
logging, tenant scoping, and invalid-input handling."""

import uuid
from datetime import datetime, timezone

import pytest

from app.models import Business, Customer, Lead, LeadEvent, User
from app.services.leads import (
    CustomerNotFoundError,
    InvalidAssigneeError,
    LeadAlreadyExistsError,
    LeadNotFoundError,
    create_lead,
    delete_lead,
    get_lead_for_customer,
    update_lead,
)


def _business_with_customer(db, name="Clinic A", phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone)
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000", display_name="Alex Rivera")
    db.add(customer)
    db.flush()
    return biz, customer


def _user(db, business_id, clerk_user_id="user_a"):
    user = User(
        business_id=business_id, clerk_user_id=clerk_user_id, email=f"{clerk_user_id}@x.com"
    )
    db.add(user)
    db.flush()
    return user


# --- create_lead --------------------------------------------------------------


def test_create_lead_defaults_and_logs_created_event(db_session):
    biz, customer = _business_with_customer(db_session)

    lead = create_lead(db_session, biz.id, customer.id)

    assert lead.stage == "new"
    assert lead.business_id == biz.id
    assert lead.customer_id == customer.id
    events = db_session.query(LeadEvent).filter(LeadEvent.lead_id == lead.id).all()
    assert len(events) == 1
    assert events[0].type == "lead_created"
    assert events[0].to_value == "new"
    assert events[0].from_value is None


def test_create_lead_with_all_fields(db_session):
    biz, customer = _business_with_customer(db_session)
    user = _user(db_session, biz.id)
    follow_up = datetime(2026, 8, 1, 10, 0)

    lead = create_lead(
        db_session,
        biz.id,
        customer.id,
        stage="contacted",
        source="whatsapp",
        estimated_value=1500.50,
        notes="Interested in premium plan",
        next_follow_up_at=follow_up,
        assigned_to=user.id,
    )

    assert lead.stage == "contacted"
    assert lead.source == "whatsapp"
    assert float(lead.estimated_value) == 1500.50
    assert lead.notes == "Interested in premium plan"
    assert lead.next_follow_up_at == follow_up
    assert lead.assigned_to == user.id


def test_create_lead_normalizes_timezone_aware_follow_up(db_session):
    biz, customer = _business_with_customer(db_session)
    aware = datetime(2026, 8, 1, 10, 0, tzinfo=timezone.utc)

    lead = create_lead(db_session, biz.id, customer.id, next_follow_up_at=aware)

    assert lead.next_follow_up_at.tzinfo is None
    assert lead.next_follow_up_at == datetime(2026, 8, 1, 10, 0)


def test_create_lead_rejects_unknown_customer(db_session):
    biz, _ = _business_with_customer(db_session)

    with pytest.raises(CustomerNotFoundError):
        create_lead(db_session, biz.id, uuid.uuid4())


def test_create_lead_is_tenant_scoped_for_customer_lookup(db_session):
    biz_a, _ = _business_with_customer(db_session, "A", phone="PN_A")
    biz_b, customer_b = _business_with_customer(db_session, "B", phone="PN_B")

    with pytest.raises(CustomerNotFoundError):
        create_lead(db_session, biz_a.id, customer_b.id)


def test_create_lead_rejects_duplicate_for_same_customer(db_session):
    biz, customer = _business_with_customer(db_session)
    create_lead(db_session, biz.id, customer.id)

    with pytest.raises(LeadAlreadyExistsError):
        create_lead(db_session, biz.id, customer.id)


def test_create_lead_race_raises_already_exists_not_integrity_error(db_session, monkeypatch):
    """Two concurrent requests can both pass the upfront existence check
    before either commits. Simulates that by forcing this call's own check
    to report "no lead yet" even though one already exists (committed by the
    "other" request) — the UNIQUE(business_id, customer_id) constraint must
    still be what stops the duplicate, and it must surface as
    LeadAlreadyExistsError (-> 409), not an unhandled IntegrityError."""
    import app.services.leads as leads_module

    biz, customer = _business_with_customer(db_session)
    winner = create_lead(db_session, biz.id, customer.id, stage="new")

    monkeypatch.setattr(leads_module, "get_lead_for_customer", lambda *a, **k: None)

    with pytest.raises(LeadAlreadyExistsError):
        create_lead(db_session, biz.id, customer.id, stage="contacted")

    # The loser's attempt didn't leave a half-created row behind, and the
    # winner is untouched.
    remaining = db_session.query(Lead).filter_by(business_id=biz.id, customer_id=customer.id).all()
    assert len(remaining) == 1
    assert remaining[0].id == winner.id
    assert remaining[0].stage == "new"


def test_create_lead_rejects_invalid_assignee(db_session):
    biz, customer = _business_with_customer(db_session)

    with pytest.raises(InvalidAssigneeError):
        create_lead(db_session, biz.id, customer.id, assigned_to=uuid.uuid4())


def test_create_lead_rejects_assignee_from_another_business(db_session):
    biz_a, customer_a = _business_with_customer(db_session, "A", phone="PN_A")
    biz_b, _ = _business_with_customer(db_session, "B", phone="PN_B")
    other_user = _user(db_session, biz_b.id, "user_b")

    with pytest.raises(InvalidAssigneeError):
        create_lead(db_session, biz_a.id, customer_a.id, assigned_to=other_user.id)


# --- update_lead ---------------------------------------------------------------


def test_update_lead_changes_stage_and_logs_event(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)

    result = update_lead(db_session, biz.id, lead.id, {"stage": "contacted"})

    assert result.stage == "contacted"
    event = (
        db_session.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id, LeadEvent.type == "stage_change")
        .one()
    )
    assert event.from_value == "new"
    assert event.to_value == "contacted"


def test_update_lead_notes_logs_notes_updated_event(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id, notes="first note")

    update_lead(db_session, biz.id, lead.id, {"notes": "second note"})

    event = (
        db_session.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id, LeadEvent.type == "notes_updated")
        .one()
    )
    assert event.from_value == "first note"
    assert event.to_value == "second note"


def test_update_lead_follow_up_logs_follow_up_set_event(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)
    new_follow_up = datetime(2026, 9, 1, 9, 0)

    update_lead(db_session, biz.id, lead.id, {"next_follow_up_at": new_follow_up})

    event = (
        db_session.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id, LeadEvent.type == "follow_up_set")
        .one()
    )
    assert event.from_value is None
    # Sprint 77: _stringify() now goes through to_iso_utc, so the timeline's
    # own `new Date(item.to_value)` (frontend/src/components/customer-
    # detail.tsx) can't misread this as local time in a non-UTC browser.
    assert event.to_value == new_follow_up.isoformat() + "Z"


def test_update_lead_assigned_to_logs_assigned_event(db_session):
    biz, customer = _business_with_customer(db_session)
    user = _user(db_session, biz.id)
    lead = create_lead(db_session, biz.id, customer.id)

    update_lead(db_session, biz.id, lead.id, {"assigned_to": user.id})

    event = (
        db_session.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id, LeadEvent.type == "assigned")
        .one()
    )
    assert event.from_value is None
    assert event.to_value == str(user.id)


def test_update_lead_can_explicitly_clear_assigned_to(db_session):
    biz, customer = _business_with_customer(db_session)
    user = _user(db_session, biz.id)
    lead = create_lead(db_session, biz.id, customer.id, assigned_to=user.id)

    result = update_lead(db_session, biz.id, lead.id, {"assigned_to": None})

    assert result.assigned_to is None
    event = (
        db_session.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id, LeadEvent.type == "assigned")
        .order_by(LeadEvent.created_at.desc())
        .first()
    )
    assert event.from_value == str(user.id)
    assert event.to_value is None


def test_update_lead_does_not_log_event_when_value_unchanged(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id, stage="new")

    update_lead(db_session, biz.id, lead.id, {"stage": "new"})

    events = (
        db_session.query(LeadEvent)
        .filter(LeadEvent.lead_id == lead.id, LeadEvent.type == "stage_change")
        .all()
    )
    assert events == []


def test_update_lead_does_not_log_event_for_source_or_estimated_value(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)

    update_lead(db_session, biz.id, lead.id, {"source": "referral", "estimated_value": 999.0})

    events = db_session.query(LeadEvent).filter(LeadEvent.lead_id == lead.id).all()
    assert [e.type for e in events] == ["lead_created"]


def test_update_lead_rejects_unknown_lead(db_session):
    biz, _ = _business_with_customer(db_session)

    with pytest.raises(LeadNotFoundError):
        update_lead(db_session, biz.id, uuid.uuid4(), {"stage": "won"})


def test_update_lead_is_tenant_scoped(db_session):
    biz_a, customer_a = _business_with_customer(db_session, "A", phone="PN_A")
    biz_b, _ = _business_with_customer(db_session, "B", phone="PN_B")
    lead = create_lead(db_session, biz_a.id, customer_a.id)

    with pytest.raises(LeadNotFoundError):
        update_lead(db_session, biz_b.id, lead.id, {"stage": "won"})


def test_update_lead_rejects_invalid_assignee(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)

    with pytest.raises(InvalidAssigneeError):
        update_lead(db_session, biz.id, lead.id, {"assigned_to": uuid.uuid4()})


# --- delete_lead ---------------------------------------------------------------


def test_delete_lead_removes_lead_and_cascades_events(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)
    lead_id = lead.id

    assert delete_lead(db_session, biz.id, lead_id) is True

    assert db_session.get(Lead, lead_id) is None
    assert db_session.query(LeadEvent).filter(LeadEvent.lead_id == lead_id).count() == 0


def test_delete_lead_returns_false_for_unknown_lead(db_session):
    biz, _ = _business_with_customer(db_session)
    assert delete_lead(db_session, biz.id, uuid.uuid4()) is False


def test_delete_lead_is_tenant_scoped(db_session):
    biz_a, customer_a = _business_with_customer(db_session, "A", phone="PN_A")
    biz_b, _ = _business_with_customer(db_session, "B", phone="PN_B")
    lead = create_lead(db_session, biz_a.id, customer_a.id)

    assert delete_lead(db_session, biz_b.id, lead.id) is False
    assert db_session.get(Lead, lead.id) is not None


# --- get_lead_for_customer (DEC-034 — shared by create_lead, lead_tools.py, context.py) ------


def test_get_lead_for_customer_returns_the_lead(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)

    assert get_lead_for_customer(db_session, biz.id, customer.id).id == lead.id


def test_get_lead_for_customer_returns_none_when_no_lead_exists(db_session):
    biz, customer = _business_with_customer(db_session)

    assert get_lead_for_customer(db_session, biz.id, customer.id) is None


def test_get_lead_for_customer_is_tenant_scoped(db_session):
    biz_a, customer_a = _business_with_customer(db_session, "A", phone="PN_A")
    biz_b, _ = _business_with_customer(db_session, "B", phone="PN_B")
    create_lead(db_session, biz_a.id, customer_a.id)

    assert get_lead_for_customer(db_session, biz_b.id, customer_a.id) is None
