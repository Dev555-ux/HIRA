"""Tests for the protected dashboard API: auth guard + tenant isolation."""

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.dashboard import get_reply_sender
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
    customer = Customer(business_id=biz.id, wa_phone="+15551230000")
    db.add(customer)
    db.flush()
    conv = Conversation(business_id=biz.id, customer_id=customer.id)
    db.add(conv)
    db.flush()
    msg = Message(
        conversation_id=conv.id,
        business_id=biz.id,
        direction="outbound",
        body="Yes, we are open 9-5.",
        type="text",
        status="pending_approval",
    )
    db.add(msg)
    db.flush()
    return biz, user, msg


def _client(db_session, *, claims_for_token, sender=lambda *a: "wamid.out"):
    """TestClient with auth verifier + sender overridden (no Clerk, no WhatsApp)."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    app.dependency_overrides[get_reply_sender] = lambda: sender
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def test_approve_requires_authentication(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session  # no verifier override needed
    client = TestClient(app)
    resp = client.post(f"/api/v1/messages/{msg.id}/approve")  # no Authorization header
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_approve_rejects_invalid_token(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()

    def bad_verify(_token):
        raise HTTPException(status_code=401, detail="Invalid")

    client = _client(db_session, claims_for_token=bad_verify)
    resp = client.post(f"/api/v1/messages/{msg.id}/approve", headers=_auth())
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_approve_sends_and_marks_sent(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/approve", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "sent"
    app.dependency_overrides.clear()


def test_cannot_approve_another_businesss_message(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    _, _, msg_b = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()

    # Authenticated as business A, trying to approve business B's message.
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/messages/{msg_b.id}/approve", headers=_auth())

    assert resp.status_code == 404  # indistinguishable from non-existent
    db_session.refresh(msg_b)
    assert msg_b.status == "pending_approval"  # untouched
    app.dependency_overrides.clear()


def test_pending_list_is_tenant_scoped(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/pending", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1  # only business A's pending message
    app.dependency_overrides.clear()


def test_unknown_user_is_rejected(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_ghost"})
    resp = client.get("/api/v1/pending", headers=_auth())
    assert resp.status_code == 401
    app.dependency_overrides.clear()
