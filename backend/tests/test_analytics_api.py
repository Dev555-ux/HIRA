"""Tests for the Analytics API (/api/v1/analytics/dashboard) — the
business-scoped dashboard endpoint (Analytics Phase 1). Auth/tenant-scoping
follow the same pattern as tests/test_leads_api.py; the aggregation math
itself is already covered by tests/test_analytics_service.py, so these tests
focus on wiring: auth, tenant isolation, empty vs. populated businesses, and
range validation.
"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Message, User


def _seed_business(db, name, clerk_user_id, phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone)
    db.add(biz)
    db.flush()
    user = User(business_id=biz.id, clerk_user_id=clerk_user_id, email=f"{name}@x.com")
    db.add(user)
    db.flush()
    return biz, user


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_requires_authentication(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/api/v1/analytics/dashboard")

    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_dashboard_for_empty_business_returns_zeroed_shape(db_session):
    _seed_business(db_session, "Empty Co", "user_empty")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_empty"})
    resp = client.get("/api/v1/analytics/dashboard", headers=_auth())
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {
        "range",
        "overview",
        "trends",
        "ai_impact",
        "ai_performance",
        "business_health",
    }
    assert body["overview"]["total_conversations"] == 0
    assert body["overview"]["avg_response_time_seconds"] is None
    assert body["ai_impact"]["conversations_handled"] == 0
    assert body["ai_impact"]["estimated_hours_saved"] == 0
    assert body["ai_performance"]["total_turns"] == 0
    assert body["business_health"]["conversations_by_status"] == {}
    assert len(body["trends"]["conversations"]) == 31  # 30d default, inclusive


def test_dashboard_for_populated_business_reflects_real_activity(db_session):
    biz, _ = _seed_business(db_session, "Busy Co", "user_busy")
    cust = Customer(business_id=biz.id, wa_phone="+10000000000")
    db_session.add(cust)
    db_session.flush()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    conv = Conversation(business_id=biz.id, customer_id=cust.id, status="active", created_at=now)
    db_session.add(conv)
    db_session.flush()
    db_session.add(
        Message(
            business_id=biz.id,
            conversation_id=conv.id,
            direction="inbound",
            body="hi",
            created_at=now,
        )
    )
    db_session.add(
        Message(
            business_id=biz.id,
            conversation_id=conv.id,
            direction="outbound",
            body="hello, how can I help?",
            created_at=now,
        )
    )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_busy"})
    resp = client.get("/api/v1/analytics/dashboard?range=7d", headers=_auth())
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["range"] == "7d"
    assert body["overview"]["total_conversations"] == 1
    assert body["ai_impact"]["ai_responses"] == 1
    assert body["business_health"]["conversations_by_status"] == {"active": 1}
    assert len(body["trends"]["messages"]) == 8  # 7d default, inclusive


def test_dashboard_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_a = Customer(business_id=biz_a.id, wa_phone="+10000001")
    cust_b = Customer(business_id=biz_b.id, wa_phone="+10000002")
    db_session.add_all([cust_a, cust_b])
    db_session.flush()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db_session.add(Conversation(business_id=biz_a.id, customer_id=cust_a.id, created_at=now))
    db_session.add(Conversation(business_id=biz_b.id, customer_id=cust_b.id, created_at=now))
    db_session.add(Conversation(business_id=biz_b.id, customer_id=cust_b.id, created_at=now))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/analytics/dashboard", headers=_auth())
    app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["overview"]["total_conversations"] == 1


def test_dashboard_accepts_every_documented_range(db_session):
    _seed_business(db_session, "Range Co", "user_range")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_range"})

    for range_value, expected_days in (("7d", 8), ("30d", 31), ("90d", 91)):
        resp = client.get(f"/api/v1/analytics/dashboard?range={range_value}", headers=_auth())
        assert resp.status_code == 200
        assert resp.json()["range"] == range_value
        assert len(resp.json()["trends"]["conversations"]) == expected_days

    app.dependency_overrides.clear()


def test_dashboard_rejects_invalid_range(db_session):
    _seed_business(db_session, "Bad Range Co", "user_bad_range")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_bad_range"})

    resp = client.get("/api/v1/analytics/dashboard?range=1y", headers=_auth())
    app.dependency_overrides.clear()

    assert resp.status_code == 422
