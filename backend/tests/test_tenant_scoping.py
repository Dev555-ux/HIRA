"""Proves multi-tenant isolation: one business cannot read another's data."""

import uuid

from app.db.tenant import get_scoped, tenant_query
from app.models import Business, Customer


def _make_business(db, name):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def test_tenant_query_only_returns_owning_business_rows(db_session):
    biz_a = _make_business(db_session, "Clinic A")
    biz_b = _make_business(db_session, "Salon B")
    db_session.add(Customer(business_id=biz_a.id, wa_phone="+10000000001"))
    db_session.add(Customer(business_id=biz_b.id, wa_phone="+10000000002"))
    db_session.flush()

    a_customers = db_session.scalars(tenant_query(Customer, biz_a.id)).all()

    assert len(a_customers) == 1
    assert a_customers[0].wa_phone == "+10000000001"


def test_get_scoped_blocks_cross_tenant_access(db_session):
    biz_a = _make_business(db_session, "Clinic A")
    biz_b = _make_business(db_session, "Salon B")
    b_customer = Customer(business_id=biz_b.id, wa_phone="+10000000002")
    db_session.add(b_customer)
    db_session.flush()

    # Business A tries to read Business B's customer by id -> must be denied.
    leaked = get_scoped(db_session, Customer, biz_a.id, b_customer.id)
    assert leaked is None

    # Owner can read its own row.
    owned = get_scoped(db_session, Customer, biz_b.id, b_customer.id)
    assert owned is not None


def test_unscoped_model_raises(db_session):
    import pytest

    with pytest.raises(ValueError):
        tenant_query(Business, uuid.uuid4())  # Business itself has no business_id
