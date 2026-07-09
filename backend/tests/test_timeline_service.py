"""Unit tests for app/services/timeline.py: merging Message + LeadEvent
history into one chronological, paginated, tenant-scoped timeline."""

from datetime import datetime

from app.models import Business, Conversation, Customer, Message
from app.services.leads import create_lead, update_lead
from app.services.timeline import get_customer_timeline


def _business_with_customer(db, name="Clinic A", phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone)
    db.add(biz)
    db.flush()
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    return biz, customer


def _conversation(db, business_id, customer_id):
    conv = Conversation(business_id=business_id, customer_id=customer_id)
    db.add(conv)
    db.flush()
    return conv


def _message(db, conversation_id, business_id, *, body, created_at, direction="inbound"):
    msg = Message(
        conversation_id=conversation_id,
        business_id=business_id,
        direction=direction,
        body=body,
        status="received" if direction == "inbound" else "sent",
        created_at=created_at,
    )
    db.add(msg)
    db.flush()
    return msg


def test_timeline_is_empty_for_a_customer_with_no_activity(db_session):
    biz, customer = _business_with_customer(db_session)

    items, total = get_customer_timeline(db_session, biz.id, customer.id, limit=20, offset=0)

    assert items == []
    assert total == 0


def test_timeline_includes_messages(db_session):
    biz, customer = _business_with_customer(db_session)
    conv = _conversation(db_session, biz.id, customer.id)
    _message(db_session, conv.id, biz.id, body="hello", created_at=datetime(2026, 7, 1, 9, 0))
    _message(db_session, conv.id, biz.id, body="hi there", created_at=datetime(2026, 7, 1, 9, 5))

    items, total = get_customer_timeline(db_session, biz.id, customer.id, limit=20, offset=0)

    assert total == 2
    assert [i["type"] for i in items] == ["message", "message"]
    # newest-first
    assert items[0]["body"] == "hi there"
    assert items[1]["body"] == "hello"


def test_timeline_includes_lead_events(db_session):
    biz, customer = _business_with_customer(db_session)
    lead = create_lead(db_session, biz.id, customer.id)
    update_lead(db_session, biz.id, lead.id, {"stage": "contacted"})

    items, total = get_customer_timeline(db_session, biz.id, customer.id, limit=20, offset=0)

    assert total == 2  # lead_created + stage_change
    assert all(i["type"] == "lead_event" for i in items)
    assert items[0]["event_type"] == "stage_change"
    assert items[1]["event_type"] == "lead_created"


def test_timeline_merges_messages_and_lead_events_chronologically(db_session):
    biz, customer = _business_with_customer(db_session)
    conv = _conversation(db_session, biz.id, customer.id)
    _message(
        db_session, conv.id, biz.id, body="are you open?", created_at=datetime(2026, 7, 1, 9, 0)
    )
    _message(
        db_session,
        conv.id,
        biz.id,
        body="yes we are",
        created_at=datetime(2026, 7, 1, 9, 10),
        direction="outbound",
    )
    # LeadEvent.created_at uses server_default=now() (real wall-clock time),
    # which sorts after both messages' fixed 2026-07-01 timestamps.
    create_lead(db_session, biz.id, customer.id)

    items, total = get_customer_timeline(db_session, biz.id, customer.id, limit=20, offset=0)

    assert total == 3  # 2 messages + 1 lead_created event
    types = [i["type"] for i in items]
    assert types[0] == "lead_event"  # newest — created just now
    assert types[1] == "message"
    assert items[1]["body"] == "yes we are"
    assert types[2] == "message"
    assert items[2]["body"] == "are you open?"


def test_timeline_pagination_across_both_sources(db_session):
    biz, customer = _business_with_customer(db_session)
    conv = _conversation(db_session, biz.id, customer.id)
    for i in range(5):
        _message(db_session, conv.id, biz.id, body=f"msg{i}", created_at=datetime(2026, 7, 1, 9, i))

    page1, total = get_customer_timeline(db_session, biz.id, customer.id, limit=2, offset=0)
    page2, _ = get_customer_timeline(db_session, biz.id, customer.id, limit=2, offset=2)

    assert total == 5
    assert len(page1) == 2
    assert len(page2) == 2
    assert page1[0]["body"] == "msg4"  # newest first
    assert page1[1]["body"] == "msg3"
    assert page2[0]["body"] == "msg2"
    assert page2[1]["body"] == "msg1"


def test_timeline_is_tenant_scoped(db_session):
    biz_a, customer_a = _business_with_customer(db_session, "A", phone="PN_A")
    biz_b, _ = _business_with_customer(db_session, "B", phone="PN_B")
    conv_a = _conversation(db_session, biz_a.id, customer_a.id)
    _message(db_session, conv_a.id, biz_a.id, body="hi", created_at=datetime(2026, 7, 1, 9, 0))

    # Wrong business for this customer -> sees nothing, even though the
    # customer_id is valid for business A.
    items, total = get_customer_timeline(db_session, biz_b.id, customer_a.id, limit=20, offset=0)

    assert items == []
    assert total == 0


def test_timeline_scoped_to_the_right_customer(db_session):
    biz, customer_a = _business_with_customer(db_session, "A")
    customer_b = Customer(business_id=biz.id, wa_phone="+15559998888")
    db_session.add(customer_b)
    db_session.flush()
    conv_a = _conversation(db_session, biz.id, customer_a.id)
    conv_b = _conversation(db_session, biz.id, customer_b.id)
    _message(db_session, conv_a.id, biz.id, body="from A", created_at=datetime(2026, 7, 1, 9, 0))
    _message(db_session, conv_b.id, biz.id, body="from B", created_at=datetime(2026, 7, 1, 9, 0))

    items, total = get_customer_timeline(db_session, biz.id, customer_a.id, limit=20, offset=0)

    assert total == 1
    assert items[0]["body"] == "from A"
