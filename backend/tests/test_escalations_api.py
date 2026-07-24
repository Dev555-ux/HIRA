"""Tests for the Escalation Queue API (/api/v1/escalations): list/filter,
assign/unassign (self-claim), resolve — tenant isolation throughout."""

import threading

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.escalations import assign_escalation
from app.auth.dependencies import Principal, get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Escalation, User
from tests.conftest import TEST_DATABASE_URL


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


def test_assign_returns_409_when_already_assigned_to_another_user(db_session):
    biz, user_a = _seed_business(db_session, "A", "user_a")
    user_b = User(business_id=biz.id, clerk_user_id="user_b", email="user_b@x.com")
    db_session.add(user_b)
    db_session.flush()
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id, assigned_to=user_a.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/assign", headers=_auth())

    assert resp.status_code == 409
    db_session.refresh(escalation)
    assert escalation.assigned_to == user_a.id  # unchanged — not overwritten
    app.dependency_overrides.clear()


def test_assign_is_idempotent_when_reclaiming_your_own_assignment(db_session):
    biz, user = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id, assigned_to=user.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/assign", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["assigned_to"]["id"] == str(user.id)
    app.dependency_overrides.clear()


def test_concurrent_assign_only_one_wins(db_session):
    """Two team members racing to claim the same escalation must not both
    succeed — release-review regression for the assign collision race."""
    biz, user_a = _seed_business(db_session, "A", "user_a")
    user_b = User(business_id=biz.id, clerk_user_id="user_b", email="user_b@x.com")
    db_session.add(user_b)
    db_session.flush()
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id)
    db_session.commit()
    escalation_id, business_id = escalation.id, biz.id
    user_a_id, user_b_id = user_a.id, user_b.id

    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    results: dict[str, int] = {}
    start_barrier = threading.Barrier(2)

    def worker(name, user_id):
        session = test_sessionmaker()
        principal = Principal(
            user_id=user_id, business_id=business_id, clerk_user_id=name, role="owner"
        )
        start_barrier.wait(timeout=5)
        try:
            assign_escalation(escalation_id, principal=principal, db=session)
            results[name] = 200
        except Exception as exc:  # HTTPException
            results[name] = getattr(exc, "status_code", -1)
        finally:
            session.close()

    threads = [
        threading.Thread(target=worker, args=("A", user_a_id)),
        threading.Thread(target=worker, args=("B", user_b_id)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert sorted(results.values()) == [200, 409]  # exactly one winner, one conflict

    db_session.expire_all()
    final = db_session.get(Escalation, escalation_id)
    assert final.assigned_to in (user_a_id, user_b_id)  # exactly one claimant, never both/neither


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


def test_unassign_by_non_assignee_returns_403(db_session):
    """Release-review regression: only the user who claimed an escalation may
    unassign it — a teammate can't silently clear someone else's claim."""
    biz, user_a = _seed_business(db_session, "A", "user_a")
    user_b = User(business_id=biz.id, clerk_user_id="user_b", email="user_b@x.com")
    db_session.add(user_b)
    db_session.flush()
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id, assigned_to=user_a.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/unassign", headers=_auth())

    assert resp.status_code == 403
    db_session.refresh(escalation)
    assert escalation.assigned_to == user_a.id  # unchanged
    app.dependency_overrides.clear()


def test_unassign_when_unclaimed_returns_403(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id)  # never assigned
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/unassign", headers=_auth())

    assert resp.status_code == 403
    app.dependency_overrides.clear()


def test_unassign_another_businesss_escalation_404s_not_403(db_session):
    """Tenant isolation must win over the ownership check: unassigning
    another business's escalation looks identical to a nonexistent one."""
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, user_b = _seed_business(db_session, "B", "user_b")
    conv_b, _ = _conversation(db_session, biz_b.id, wa_phone="+10000002")
    escalation_b = _escalation(db_session, biz_b.id, conv_b.id, assigned_to=user_b.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation_b.id}/unassign", headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(escalation_b)
    assert escalation_b.assigned_to == user_b.id
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


def test_resolve_clears_the_conversations_escalated_status(db_session):
    """Release-review regression: resolving an escalation must clear
    Conversation.status, or the conversation is stuck out of the Inbox's
    Open filter and stuck in its Escalated filter forever."""
    biz, _ = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)  # starts "escalated"
    escalation = _escalation(db_session, biz.id, conv.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/resolve", headers=_auth())

    assert resp.status_code == 200
    db_session.refresh(conv)
    assert conv.status == "active"
    app.dependency_overrides.clear()


def test_resolve_removes_conversation_from_escalated_filter_and_restores_open_filter(db_session):
    """Full resolve workflow across both APIs: after resolving, the Inbox's
    'open' filter must include the conversation again and its 'escalated'
    filter must no longer include it."""
    biz, _ = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    escalation = _escalation(db_session, biz.id, conv.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client.post(f"/api/v1/escalations/{escalation.id}/resolve", headers=_auth())

    open_resp = client.get("/api/v1/conversations", params={"status": "open"}, headers=_auth())
    escalated_resp = client.get(
        "/api/v1/conversations", params={"status": "escalated"}, headers=_auth()
    )

    open_ids = {c["id"] for c in open_resp.json()["data"]}
    escalated_ids = {c["id"] for c in escalated_resp.json()["data"]}
    assert str(conv.id) in open_ids
    assert str(conv.id) not in escalated_ids
    app.dependency_overrides.clear()


def test_resolve_does_not_clobber_a_conversation_that_is_no_longer_escalated(db_session):
    """If the conversation's status was already changed to something else by
    the time an escalation on it is resolved (e.g. closed), resolving must
    not blindly force it back to active."""
    biz, _ = _seed_business(db_session, "A", "user_a")
    conv, _ = _conversation(db_session, biz.id)
    conv.status = "closed"
    escalation = _escalation(db_session, biz.id, conv.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/escalations/{escalation.id}/resolve", headers=_auth())

    assert resp.status_code == 200
    db_session.refresh(conv)
    assert conv.status == "closed"
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
