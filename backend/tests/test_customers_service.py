"""Unit tests for app/services/customers.py: manual create/update/delete,
tenant scoping, duplicate-phone handling, and the create-then-insert race
(same pattern as Sprint 36's test_leads_service.py/test_provisioning.py)."""

from app.models import Business, Customer
from app.services.customers import (
    CustomerAlreadyExistsError,
    CustomerNotFoundError,
    create_customer,
    delete_customer,
    update_customer,
)


def _business(db, name="Clinic A"):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def test_create_customer_with_name_only(db_session):
    biz = _business(db_session)

    customer = create_customer(db_session, biz.id, display_name="Alex Rivera")

    assert customer.display_name == "Alex Rivera"
    assert customer.wa_phone is None
    assert customer.email is None
    assert customer.notes is None
    assert customer.business_id == biz.id


def test_create_customer_with_all_fields(db_session):
    biz = _business(db_session)

    customer = create_customer(
        db_session,
        biz.id,
        display_name="Jordan Lee",
        wa_phone="+15559876543",
        email="jordan@example.com",
        notes="Prefers afternoons",
    )

    assert customer.wa_phone == "+15559876543"
    assert customer.email == "jordan@example.com"
    assert customer.notes == "Prefers afternoons"


def test_create_customer_rejects_duplicate_phone(db_session):
    biz = _business(db_session)
    create_customer(db_session, biz.id, display_name="First", wa_phone="+15551230000")

    try:
        create_customer(db_session, biz.id, display_name="Second", wa_phone="+15551230000")
        assert False, "expected CustomerAlreadyExistsError"
    except CustomerAlreadyExistsError:
        pass


def test_create_customer_allows_multiple_customers_with_no_phone(db_session):
    biz = _business(db_session)

    first = create_customer(db_session, biz.id, display_name="First")
    second = create_customer(db_session, biz.id, display_name="Second")

    assert first.id != second.id
    assert first.wa_phone is None and second.wa_phone is None


def test_create_customer_race_raises_already_exists_not_integrity_error(db_session, monkeypatch):
    """Two concurrent requests for the same phone can both pass the upfront
    existence check before either commits. Simulates that the same way
    Sprint 36's create_lead/provision_business tests do: force this call's
    own check to report "not found" even though one already exists — the
    UNIQUE(business_id, wa_phone) constraint must still be what stops the
    duplicate, surfacing as CustomerAlreadyExistsError (-> 409), not an
    unhandled IntegrityError."""
    import app.services.customers as customers_module

    biz = _business(db_session)
    winner = create_customer(db_session, biz.id, display_name="Winner", wa_phone="+15551230000")

    monkeypatch.setattr(customers_module, "_find_by_phone", lambda *a, **k: None)

    try:
        create_customer(db_session, biz.id, display_name="Loser", wa_phone="+15551230000")
        assert False, "expected CustomerAlreadyExistsError"
    except CustomerAlreadyExistsError:
        pass

    remaining = (
        db_session.query(Customer).filter_by(business_id=biz.id, wa_phone="+15551230000").all()
    )
    assert len(remaining) == 1
    assert remaining[0].id == winner.id
    assert remaining[0].display_name == "Winner"


def test_update_customer_changes_fields(db_session):
    biz = _business(db_session)
    customer = create_customer(db_session, biz.id, display_name="Old Name")

    updated = update_customer(
        db_session, biz.id, customer.id, {"display_name": "New Name", "notes": "follow up"}
    )

    assert updated.display_name == "New Name"
    assert updated.notes == "follow up"


def test_update_customer_rejects_unknown_customer(db_session):
    biz = _business(db_session)
    import uuid

    try:
        update_customer(db_session, biz.id, uuid.uuid4(), {"notes": "x"})
        assert False, "expected CustomerNotFoundError"
    except CustomerNotFoundError:
        pass


def test_update_customer_is_tenant_scoped(db_session):
    biz_a = _business(db_session, "A")
    biz_b = _business(db_session, "B")
    customer = create_customer(db_session, biz_b.id, display_name="B's customer")

    try:
        update_customer(db_session, biz_a.id, customer.id, {"notes": "hijacked"})
        assert False, "expected CustomerNotFoundError"
    except CustomerNotFoundError:
        pass


def test_update_customer_rejects_duplicate_phone(db_session):
    biz = _business(db_session)
    create_customer(db_session, biz.id, display_name="First", wa_phone="+15551111111")
    second = create_customer(db_session, biz.id, display_name="Second", wa_phone="+15552222222")

    try:
        update_customer(db_session, biz.id, second.id, {"wa_phone": "+15551111111"})
        assert False, "expected CustomerAlreadyExistsError"
    except CustomerAlreadyExistsError:
        pass


def test_update_customer_can_set_own_phone_unchanged(db_session):
    biz = _business(db_session)
    customer = create_customer(db_session, biz.id, display_name="Alex", wa_phone="+15551230000")

    updated = update_customer(
        db_session, biz.id, customer.id, {"wa_phone": "+15551230000", "notes": "still here"}
    )

    assert updated.wa_phone == "+15551230000"
    assert updated.notes == "still here"


def test_delete_customer_removes_it(db_session):
    biz = _business(db_session)
    customer = create_customer(db_session, biz.id, display_name="Alex")

    assert delete_customer(db_session, biz.id, customer.id) is True
    assert db_session.get(Customer, customer.id) is None


def test_delete_customer_returns_false_for_unknown_customer(db_session):
    biz = _business(db_session)
    import uuid

    assert delete_customer(db_session, biz.id, uuid.uuid4()) is False


def test_delete_customer_is_tenant_scoped(db_session):
    biz_a = _business(db_session, "A")
    biz_b = _business(db_session, "B")
    customer = create_customer(db_session, biz_b.id, display_name="B's customer")

    assert delete_customer(db_session, biz_a.id, customer.id) is False
    assert db_session.get(Customer, customer.id) is not None
