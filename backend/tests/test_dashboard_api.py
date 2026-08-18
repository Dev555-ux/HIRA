"""Tests for the protected dashboard API: auth guard + tenant isolation."""

from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.llm.mock import MockProvider
from app.api.dashboard import get_reply_sender
from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, ExecutionTrace, Message, User
from app.whatsapp.credentials import store_credentials
from tests.test_knowledge_base import FakeEmbeddingProvider


@pytest.fixture(autouse=True)
def _whatsapp_encryption_key(monkeypatch):
    # Sprint 69: approve_and_send now needs a stored, encrypted
    # WhatsAppCredential (not just Business.whatsapp_phone_number_id) to
    # reach the send step — _seed_business below stores one automatically
    # whenever a phone number is given, using this key.
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


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
    if phone is not None:
        store_credentials(db, biz.id, access_token="test-token", app_secret="test-secret")
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


def _client(db_session, *, claims_for_token, sender=lambda *a, **k: "wamid.out"):
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
        sender=lambda *a, **k: sent.append(a) or "wamid.should-not-happen",
    )

    resp = client.post(f"/api/v1/messages/{msg.id}/approve", headers=_auth())

    assert resp.status_code == 409
    assert sent == []  # Meta API was never attempted
    db_session.refresh(msg)
    assert msg.status == "pending_approval"  # untouched
    app.dependency_overrides.clear()


def test_approve_returns_409_when_whatsapp_window_expired(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    conversation = db_session.get(Conversation, msg.conversation_id)
    conversation.window_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
        hours=1
    )
    db_session.commit()
    sent = []
    client = _client(
        db_session,
        claims_for_token=lambda t: {"sub": "user_a"},
        sender=lambda *a, **k: sent.append(a) or "wamid.should-not-happen",
    )

    resp = client.post(f"/api/v1/messages/{msg.id}/approve", headers=_auth())

    assert resp.status_code == 409
    assert "24-hour" in resp.json()["detail"]
    assert sent == []  # Meta API was never attempted
    db_session.refresh(msg)
    assert msg.status == "failed"
    assert msg.ai_meta["failure_reason"] == "channel_window_expired"
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


def test_edit_draft_attaches_media(db_session):
    """Sprint 65 PR 6: PATCH /messages/{id}/draft can attach media to a
    pending draft before approval — the backend-only path decided for
    this PR (no compose/upload UI yet, see PR notes)."""
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft",
        json={
            "body": "Here's a photo of the space.",
            "media": [{"kind": "image", "url": "https://cdn.example/photo.jpg"}],
        },
        headers=_auth(),
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["media"] == [
        {"kind": "image", "url": "https://cdn.example/photo.jpg", "mime_type": None, "caption": None}
    ]
    db_session.refresh(msg)
    assert msg.media == [
        {"kind": "image", "url": "https://cdn.example/photo.jpg", "mime_type": None, "caption": None}
    ]
    app.dependency_overrides.clear()


def test_edit_draft_omitted_media_leaves_existing_media_untouched(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    msg.media = [{"kind": "image", "url": "https://cdn.example/x.jpg", "mime_type": None, "caption": None}]
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft", json={"body": "just editing text"}, headers=_auth()
    )

    assert resp.status_code == 200
    db_session.refresh(msg)
    assert msg.media == [
        {"kind": "image", "url": "https://cdn.example/x.jpg", "mime_type": None, "caption": None}
    ]
    app.dependency_overrides.clear()


def test_edit_draft_empty_media_list_clears_it(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    msg.media = [{"kind": "image", "url": "https://cdn.example/x.jpg", "mime_type": None, "caption": None}]
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft", json={"body": "no more photo", "media": []}, headers=_auth()
    )

    assert resp.status_code == 200
    assert resp.json()["data"]["media"] == []
    db_session.refresh(msg)
    assert msg.media is None
    app.dependency_overrides.clear()


def test_edit_draft_rejects_unknown_media_kind(db_session):
    _, _, msg = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/messages/{msg.id}/draft",
        json={"body": "x", "media": [{"kind": "gif", "url": "https://cdn.example/x.gif"}]},
        headers=_auth(),
    )

    assert resp.status_code == 422
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
        sender=lambda *a, **k: calls.append(a) or "wamid.x",
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


# --- GET /activity (Sprint 84, Dashboard Foundation) -------------------------


def _activity_conversation(db, business, *, display_name="Priya"):
    customer = Customer(business_id=business.id, wa_phone="+15559990000", display_name=display_name)
    db.add(customer)
    db.flush()
    conv = Conversation(business_id=business.id, customer_id=customer.id)
    db.add(conv)
    db.flush()
    return conv


def _activity_result_message(db, conversation, business, *, status="sent", ai_meta=None):
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body="ok",
        type="text",
        status=status,
        ai_meta=ai_meta,
    )
    db.add(message)
    db.flush()
    return message


def _activity_trace(
    db,
    business,
    conversation,
    *,
    category="action",
    steps=None,
    result_messages=(),
):
    trace = ExecutionTrace(
        business_id=business.id,
        conversation_id=conversation.id,
        trigger_message_id=None,
        category=category,
        plan={"category": category, "steps": steps or [], "clarification_hint": None},
        proposed_tool_calls=[],
        result_message_ids=[str(m.id) for m in result_messages],
        duration_ms=100,
    )
    db.add(trace)
    db.flush()
    return trace


def test_activity_requires_authentication(db_session):
    biz, _, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.get("/api/v1/activity")

    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_activity_is_tenant_scoped(db_session):
    biz_a, _, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    conv_a = _activity_conversation(db_session, biz_a)
    conv_b = _activity_conversation(db_session, biz_b)
    _activity_trace(
        db_session,
        biz_a,
        conv_a,
        steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
        result_messages=[_activity_result_message(db_session, conv_a, biz_a)],
    )
    _activity_trace(
        db_session,
        biz_b,
        conv_b,
        steps=[{"domain": "crm", "action": "crm_lead", "role": "sales_executive"}],
        result_messages=[_activity_result_message(db_session, conv_b, biz_b)],
    )
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/activity", headers=_auth())

    assert resp.status_code == 200
    rows = resp.json()["data"]
    assert len(rows) == 1
    assert "Priya" in rows[0]["summary"]
    app.dependency_overrides.clear()


def test_activity_summarizes_a_successful_booking(db_session):
    biz, _, _ = _seed_business(db_session, "A", "user_a")
    conv = _activity_conversation(db_session, biz, display_name="Kabir")
    _activity_trace(
        db_session,
        biz,
        conv,
        steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
        result_messages=[_activity_result_message(db_session, conv, biz, status="sent")],
    )
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/activity", headers=_auth())

    row = resp.json()["data"][0]
    assert row["summary"] == "Booked an appointment for Kabir"
    assert row["outcome"] == "sent"
    assert row["customer"]["display_name"] == "Kabir"
    app.dependency_overrides.clear()


def test_activity_reflects_escalated_outcome_over_category(db_session):
    biz, _, _ = _seed_business(db_session, "A", "user_a")
    conv = _activity_conversation(db_session, biz, display_name="Morgan")
    _activity_trace(
        db_session,
        biz,
        conv,
        category="knowledge",
        result_messages=[_activity_result_message(db_session, conv, biz, status="escalated")],
    )
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/activity", headers=_auth())

    row = resp.json()["data"][0]
    assert row["summary"] == "Escalated a message from Morgan to you"
    assert row["outcome"] == "escalated"
    app.dependency_overrides.clear()


def test_activity_includes_grounding_count_for_knowledge_replies(db_session):
    biz, _, _ = _seed_business(db_session, "A", "user_a")
    conv = _activity_conversation(db_session, biz, display_name="Sam")
    _activity_trace(
        db_session,
        biz,
        conv,
        category="knowledge",
        result_messages=[
            _activity_result_message(
                db_session, conv, biz, status="sent", ai_meta={"retrieved_count": 2}
            )
        ],
    )
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/activity", headers=_auth())

    row = resp.json()["data"][0]
    assert row["summary"] == "Answered a question from Sam, grounded in 2 knowledge sources"
    app.dependency_overrides.clear()


def test_activity_drops_traces_with_no_result(db_session):
    biz, _, _ = _seed_business(db_session, "A", "user_a")
    conv = _activity_conversation(db_session, biz)
    _activity_trace(db_session, biz, conv, category="conversation", result_messages=[])
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/activity", headers=_auth())

    assert resp.json()["data"] == []
    app.dependency_overrides.clear()


def test_activity_orders_newest_first(db_session):
    biz, _, _ = _seed_business(db_session, "A", "user_a")
    conv = _activity_conversation(db_session, biz)
    older = _activity_trace(
        db_session,
        biz,
        conv,
        category="action",
        steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
        result_messages=[_activity_result_message(db_session, conv, biz)],
    )
    db_session.flush()
    older.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    newer = _activity_trace(
        db_session,
        biz,
        conv,
        category="action",
        steps=[{"domain": "crm", "action": "crm_lead", "role": "sales_executive"}],
        result_messages=[_activity_result_message(db_session, conv, biz)],
    )
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/activity", headers=_auth())

    rows = resp.json()["data"]
    assert [r["id"] for r in rows] == [str(newer.id), str(older.id)]
    app.dependency_overrides.clear()
