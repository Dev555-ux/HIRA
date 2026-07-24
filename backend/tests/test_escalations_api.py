"""Tests for the Escalation Queue API (/api/v1/escalations): list/filter,
assign/unassign (self-claim), resolve — tenant isolation throughout."""

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Escalation, User


def _seed_business(db, name, clerk_user_id):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    user = User(business_id=biz.id, clerk_user_id=clerk_user_id, email=f"{clerk_user_id}@x.com")
    db.add(user)
    db.flush()
    return biz, user


def _conversation(db, business_id, wa_phone="+10000001"):
    customer = Customer(business_id=business_id, wa_phone=wa_phone, display_name="Jamie Rivera")
    db.add(customer)
    db.flush()
    conversation = Conversation(
        business_id=business_id, customer_id=customer.id, status="escalated"
    )
    db.add(conversation)
    db.flush()
    return conversation, customer


def _escalation(db, business_id, conversation_id, *, reason="low_confidence", **kwargs):
    escalation = Escalation(
        business_id=business_id, conversation_id=conversation_id, reason=reason, **kwargs
    )
    db.add(escalation)
    db.flush()
    return escalation


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def test_list_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/escalations")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_list_returns_open_escalations_with_customer_context(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    conv, cust = _conversation(db_session, biz.id)
    _escalation(db_session, biz.id, conv.id, reason="low_confidence")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/escalations", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    row = body["data"][0]
    assert row["reason"] == "low_confidence"
    assert row["status"] == "open"
    assert row["assigned_to"] is None
    assert row["conversation"]["customer"]["display_name"] == "Jamie Rivera"
    assert body["meta"]["total"] == 1
    app.dependency_overrides.clear()


def test_list_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    conv_a, _ = _conversation(db_session, biz_a.id)
    conv_b, _ = _conversation(db_session, biz_b.id, wa_phone="+10000002")
    _escalation(db_session, biz_a.id, conv_a.id)
    _escalation(db_session, biz_b.id, conv_b.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/escalations", headers=_auth())

    assert len(resp.json()["data"]) == 1
    app.dependency_overrides.clear()


def test_list_filters_by_status(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    _escalation(db_session, biz.id, conv.id, status="open")
    _escalation(db_session, biz.id, conv.id, status="resolved")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/escalations", params={"status": "resolved"}, headers=_auth())

    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["status"] == "resolved"
    app.dependency_overrides.clear()


def test_list_filters_by_unassigned(db_session):
    biz, user = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    _escalation(db_session, biz.id, conv.id)
    _escalation(db_session, biz.id, conv.id, assigned_to=user.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/escalations", params={"assigned": "unassigned"}, headers=_auth())

    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["assigned_to"] is None
    app.dependency_overrides.clear()


def test_list_filters_by_mine(db_session):
    biz, user = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    _escalation(db_session, biz.id, conv.id)
    mine = _escalation(db_session, biz.id, conv.id, assigned_to=user.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/escalations", params={"assigned": "mine"}, headers=_auth())

    assert len(resp.json()["data"]) == 1
    assert resp.json()["data"][0]["id"] == str(mine.id)
    assert resp.json()["data"][0]["assigned_to"]["email"] == "user_a@x.com"
    app.dependency_overrides.clear()


def test_assign_claims_for_the_calling_user(db_session):
    biz, user = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/assign", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["assigned_to"]["id"] == str(user.id)
    assert data["assigned_to"]["email"] == "user_a@x.com"
    db_session.refresh(escalation)
    assert escalation.assigned_to == user.id
    app.dependency_overrides.clear()


def test_assign_another_businesss_escalation_404s(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    conv_b, _ = _conversation(db_session, biz_b.id, wa_phone="+10000002")
    escalation_b = _escalation(db_session, biz_b.id, conv_b.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation_b.id}/assign", headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(escalation_b)
    assert escalation_b.assigned_to is None
    app.dependency_overrides.clear()


def test_unassign_clears_the_claim(db_session):
    biz, user = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id, assigned_to=user.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/unassign", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["assigned_to"] is None
    db_session.refresh(escalation)
    assert escalation.assigned_to is None
    app.dependency_overrides.clear()


def test_resolve_sets_status_resolver_and_timestamp(db_session):
    biz, user = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/resolve", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "resolved"
    assert data["resolved_by"]["id"] == str(user.id)
    assert data["resolved_at"] is not None
    db_session.refresh(escalation)
    assert escalation.status == "resolved"
    assert escalation.resolved_by == user.id
    assert escalation.resolved_at is not None
    app.dependency_overrides.clear()


def test_resolve_another_businesss_escalation_404s(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    conv_b, _ = _conversation(db_session, biz_b.id, wa_phone="+10000002")
    escalation_b = _escalation(db_session, biz_b.id, conv_b.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation_b.id}/resolve", headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(escalation_b)
    assert escalation_b.status == "open"
    app.dependency_overrides.clear()
