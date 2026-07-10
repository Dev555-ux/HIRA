"""Tests for the protected dashboard API: auth guard + tenant isolation."""

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.llm.mock import MockProvider
from app.api.dashboard import get_reply_sender
from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Message, User
from tests.test_knowledge_base import FakeEmbeddingProvider


def _mock_ai_providers(monkeypatch, *, fixed_reply="Yes, we're open weekends 10-2."):
    """Deterministic, offline LLM + embedding providers for regenerate tests —
    same pattern as test_playground_api.py's _mock_providers."""
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply=fixed_reply),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )


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


def test_approve_returns_409_when_whatsapp_not_connected(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a", phone=None)
    db_session.commit()
    sent = []
    client = _client(
        db_session,
        claims_for_token=lambda t: {"sub": "user_a"},
        sender=lambda *a: sent.append(a) or "wamid.should-not-happen",
    )

    resp = client.post(f"/api/v1/messages/{msg.id}/approve", headers=_auth())

    assert resp.status_code == 409
    assert sent == []  # Meta API was never attempted
    db_session.refresh(msg)
    assert msg.status == "pending_approval"  # untouched
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
    body = resp.json()
    data = body["data"]
    assert len(data) == 1  # only business A's pending message
    assert body["meta"] == {"total": 1, "limit": 200, "offset": 0}
    app.dependency_overrides.clear()


def test_pending_list_supports_limit_and_offset(db_session):
    biz, user, _first_msg = _seed_business(db_session, "A", "user_a")
    conversation = db_session.scalars(
        select(Conversation).where(Conversation.business_id == biz.id)
    ).first()
    for i in range(3):
        db_session.add(
            Message(
                conversation_id=conversation.id,
                business_id=biz.id,
                direction="outbound",
                body=f"extra reply {i}",
                type="text",
                status="pending_approval",
            )
        )
    db_session.commit()
    # 4 pending messages total now (1 from _seed_business + 3 extra).

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/pending", params={"limit": 2, "offset": 1}, headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 4, "limit": 2, "offset": 1}
    app.dependency_overrides.clear()


def test_unknown_user_is_rejected(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_ghost"})
    resp = client.get("/api/v1/pending", headers=_auth())
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_pending_list_includes_customer_and_conversation_preview(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    conversation = db_session.get(Conversation, msg.conversation_id)
    db_session.add(
        Message(
            conversation_id=conversation.id,
            business_id=conversation.business_id,
            direction="inbound",
            body="are you open today?",
            type="text",
            status="received",
        )
    )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/pending", headers=_auth())

    assert resp.status_code == 200
    reply = resp.json()["data"][0]
    assert reply["customer"]["wa_phone"] == "+15551230000"
    assert reply["conversation_preview"] == "are you open today?"
    app.dependency_overrides.clear()


# --- PATCH /messages/{id}/draft (Phase 1: editable drafts) -------------------


def test_edit_draft_updates_body(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft", json={"body": "We're open 24/7."}, headers=_auth()
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["body"] == "We're open 24/7."
    assert resp.json()["data"]["status"] == "pending_approval"
    app.dependency_overrides.clear()


def test_edit_draft_rejects_blank_body(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(f"/api/v1/messages/{msg.id}/draft", json={"body": "   "}, headers=_auth())

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_edit_draft_rejects_oversized_body(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft", json={"body": "x" * 4097}, headers=_auth()
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_edit_draft_rejects_already_approved_message(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    msg.status = "sent"
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft", json={"body": "edited"}, headers=_auth()
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_edit_draft_is_tenant_scoped(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    _, _, msg_b = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch(
        f"/api/v1/messages/{msg_b.id}/draft", json={"body": "edited"}, headers=_auth()
    )

    assert resp.status_code == 404
    db_session.refresh(msg_b)
    assert msg_b.body != "edited"
    app.dependency_overrides.clear()


def test_edit_draft_requires_authentication(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.patch(f"/api/v1/messages/{msg.id}/draft", json={"body": "edited"})
    assert resp.status_code == 401
    app.dependency_overrides.clear()


# --- POST /messages/{id}/reject (Phase 2) ------------------------------------


def test_reject_marks_rejected(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/reject", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"
    app.dependency_overrides.clear()


def test_reject_never_sends_whatsapp_message(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    calls = []
    client = _client(
        db_session,
        claims_for_token=lambda t: {"sub": "user_a"},
        sender=lambda *a: calls.append(a) or "wamid.x",
    )

    client.post(f"/api/v1/messages/{msg.id}/reject", headers=_auth())

    assert calls == []
    app.dependency_overrides.clear()


def test_reject_is_tenant_scoped(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    _, _, msg_b = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/messages/{msg_b.id}/reject", headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(msg_b)
    assert msg_b.status == "pending_approval"
    app.dependency_overrides.clear()


def test_reject_rejects_already_approved_message(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    msg.status = "sent"
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/reject", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- POST /messages/{id}/regenerate (Phase 3) --------------------------------


def _seed_business_with_history(db, name, clerk_user_id, phone="PN1"):
    biz, user, msg = _seed_business(db, name, clerk_user_id, phone=phone)
    db.add(
        Message(
            conversation_id=msg.conversation_id,
            business_id=biz.id,
            direction="inbound",
            body="are you open on weekends?",
            type="text",
            status="received",
        )
    )
    db.flush()
    return biz, user, msg


def test_regenerate_replaces_draft_body(db_session, monkeypatch):
    _mock_ai_providers(monkeypatch)
    _, _, msg = _seed_business_with_history(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/regenerate", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "pending_approval"
    assert data["body"] == "Yes, we're open weekends 10-2."
    app.dependency_overrides.clear()


def test_regenerate_is_tenant_scoped(db_session, monkeypatch):
    _mock_ai_providers(monkeypatch)
    _seed_business_with_history(db_session, "A", "user_a", phone="PN_A")
    _, _, msg_b = _seed_business_with_history(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/messages/{msg_b.id}/regenerate", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_regenerate_rejects_already_approved_message(db_session, monkeypatch):
    _mock_ai_providers(monkeypatch)
    _, _, msg = _seed_business_with_history(db_session, "A", "user_a")
    msg.status = "sent"
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/regenerate", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_regenerate_without_customer_message_returns_404(db_session, monkeypatch):
    _mock_ai_providers(monkeypatch)
    # _seed_business (no history helper) leaves no inbound message in the conversation.
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/regenerate", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- POST /messages/{id}/escalate (Phase 4) ----------------------------------


def test_escalate_creates_escalation_and_marks_conversation(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/escalate", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "escalated"
    assert data["escalation"]["status"] == "open"
    conversation = db_session.get(Conversation, msg.conversation_id)
    assert conversation.status == "escalated"
    app.dependency_overrides.clear()


def test_escalate_is_tenant_scoped(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    _, _, msg_b = _seed_business(db_session, "B", "user_b", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/messages/{msg_b.id}/escalate", headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(msg_b)
    assert msg_b.status == "pending_approval"
    app.dependency_overrides.clear()


def test_escalate_rejects_already_approved_message(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    msg.status = "sent"
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(f"/api/v1/messages/{msg.id}/escalate", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()
