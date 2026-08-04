"""Tests for the new per-business aggregations in app/services/analytics.py
(trends, ai_impact, status_breakdown) that power the Analytics dashboard
endpoint. conversation_counts/message_stats/etc. are already covered via
tests/test_founder_ops.py (business_id=None case) — this file exercises the
business_id-scoped case and the metrics that have no founder_ops equivalent.
"""

from datetime import datetime, timedelta, timezone

from app.models import Appointment, Business, Conversation, Customer, Escalation, Lead, Message
from app.services.analytics import ai_impact, fill_daily, status_breakdown, trends


def _business(db, name="Biz") -> Business:
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def _customer(db, biz) -> Customer:
    cust = Customer(business_id=biz.id, wa_phone="+10000000000")
    db.add(cust)
    db.flush()
    return cust


def test_fill_daily_produces_gap_free_series():
    since = datetime(2026, 1, 1)
    until = datetime(2026, 1, 3)
    counts = {datetime(2026, 1, 2).date(): 5}

    series = fill_daily(counts, since, until)

    assert [row["date"] for row in series] == ["2026-01-01", "2026-01-02", "2026-01-03"]
    assert [row["count"] for row in series] == [0, 5, 0]


def test_trends_counts_only_the_given_business_within_range(db_session):
    biz_a = _business(db_session, "A")
    biz_b = _business(db_session, "B")
    cust_a = _customer(db_session, biz_a)
    cust_b = _customer(db_session, biz_b)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since, until = now - timedelta(days=2), now

    db_session.add(Conversation(business_id=biz_a.id, customer_id=cust_a.id, created_at=now))
    db_session.add(Conversation(business_id=biz_b.id, customer_id=cust_b.id, created_at=now))
    db_session.add(
        Conversation(
            business_id=biz_a.id, customer_id=cust_a.id, created_at=now - timedelta(days=10)
        )
    )
    db_session.commit()

    result = trends(db_session, biz_a.id, since=since, until=until)

    assert sum(row["count"] for row in result["conversations"]) == 1
    assert len(result["conversations"]) == 3
    assert set(result.keys()) == {"conversations", "messages", "leads", "appointments"}


def test_ai_impact_counts_business_scoped_activity_in_range(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since, until = now - timedelta(days=1), now

    biz = _business(db_session)
    cust = _customer(db_session, biz)
    conv = Conversation(business_id=biz.id, customer_id=cust.id, created_at=now)
    db_session.add(conv)
    db_session.flush()

    db_session.add(
        Message(
            business_id=biz.id,
            conversation_id=conv.id,
            direction="outbound",
            body="hi",
            ai_meta={"retrieved_count": 2},
            created_at=now,
        )
    )
    db_session.add(
        Message(
            business_id=biz.id,
            conversation_id=conv.id,
            direction="outbound",
            body="hi again",
            ai_meta={"retrieved_count": 0},
            created_at=now,
        )
    )
    db_session.add(
        Escalation(business_id=biz.id, conversation_id=conv.id, reason="test", created_at=now)
    )
    db_session.add(Lead(business_id=biz.id, customer_id=cust.id, created_at=now))
    db_session.add(
        Appointment(
            business_id=biz.id,
            customer_id=cust.id,
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            created_at=now,
        )
    )
    db_session.commit()

    result = ai_impact(db_session, biz.id, since=since, until=until)

    assert result["conversations_handled"] == 1
    assert result["ai_responses"] == 2
    assert result["kb_grounded_replies"] == 1
    assert result["human_escalations"] == 1
    assert result["leads_created"] == 1
    assert result["appointments_booked"] == 1
    assert result["estimated_hours_saved"] > 0


def test_status_breakdown_is_scoped_per_business(db_session):
    biz_a = _business(db_session, "A")
    biz_b = _business(db_session, "B")
    cust_a = _customer(db_session, biz_a)
    cust_b = _customer(db_session, biz_b)

    db_session.add(Conversation(business_id=biz_a.id, customer_id=cust_a.id, status="active"))
    db_session.add(Conversation(business_id=biz_a.id, customer_id=cust_a.id, status="active"))
    db_session.add(Conversation(business_id=biz_a.id, customer_id=cust_a.id, status="closed"))
    db_session.add(Conversation(business_id=biz_b.id, customer_id=cust_b.id, status="escalated"))
    db_session.commit()

    result = status_breakdown(db_session, Conversation, Conversation.status, biz_a.id)

    assert result == {"active": 2, "closed": 1}
