"""Tests for the Conversations API (Inbox backend): auth, tenant isolation,
search, status filtering, pagination, and message-thread ordering."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Message, User

NOW = datetime(2026, 7, 10, 12, 0, tzinfo=timezone.utc)


def _seed_business(db, name, clerk_user_id, phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone)
    db.add(biz)
    db.flush()
    user = User(business_id=biz.id, clerk_user_id=clerk_user_id, email=f"{name}@x.com")
    db.add(user)
    db.flush()
    return biz, user


def _customer(db, business_id, *, wa_phone, display_name=None):
    customer = Customer(business_id=business_id, wa_phone=wa_phone, display_name=display_name)
    db.add(customer)
    db.flush()
    return customer


def _conversation(
    db, business_id, customer_id, *, conv_status="active", last_message_at=None, channel="whatsapp"
):
    conv = Conversation(
        business_id=business_id,
        customer_id=customer_id,
        status=conv_status,
        last_message_at=last_message_at,
        channel=channel,
    )
    db.add(conv)
    db.flush()
    return conv


def _message(
    db,
    conversation_id,
    business_id,
    *,
    direction="inbound",
    body="hi",
    msg_status="received",
    created_at=None,
):
    msg = Message(
        conversation_id=conversation_id,
        business_id=business_id,
        direction=direction,
        body=body,
        status=msg_status,
        created_at=created_at or NOW,
    )
    db.add(msg)
    db.flush()
    return msg


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


# --- auth + tenant isolation ------------------------------------------------


def test_list_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/conversations")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_list_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_a = _customer(db_session, biz_a.id, wa_phone="+10000001")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    _conversation(db_session, biz_a.id, cust_a.id)
    _conversation(db_session, biz_b.id, cust_b.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["wa_phone"] == "+10000001"
    app.dependency_overrides.clear()


def test_list_excludes_demo_chat_conversation(db_session):
    # Regression: Demo Chat's synthetic customer (wa_phone="__playground__",
    # app/ai/playground.py) must never appear beside real customers in the
    # Inbox — it previously did, since this query only filtered by
    # business_id.
    biz, _ = _seed_business(db_session, "A", "user_a")
    real_customer = _customer(db_session, biz.id, wa_phone="+10000001")
    demo_customer = _customer(
        db_session, biz.id, wa_phone="__playground__", display_name="Demo Chat"
    )
    _conversation(db_session, biz.id, real_customer.id)
    _conversation(db_session, biz.id, demo_customer.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["wa_phone"] == "+10000001"
    app.dependency_overrides.clear()


def test_get_conversation_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(f"/api/v1/conversations/{conv.id}")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_cannot_get_another_businesss_conversation(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    conv_b = _conversation(db_session, biz_b.id, cust_b.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv_b.id}", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_get_unknown_conversation_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations/00000000-0000-0000-0000-000000000000", headers=_auth())
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_cannot_list_messages_of_another_businesss_conversation(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    conv_b = _conversation(db_session, biz_b.id, cust_b.id)
    _message(db_session, conv_b.id, biz_b.id, body="secret")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv_b.id}/messages", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- search ------------------------------------------------------------


def test_search_matches_display_name(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    alice = _customer(db_session, biz.id, wa_phone="+10000001", display_name="Alice Smith")
    bob = _customer(db_session, biz.id, wa_phone="+10000002", display_name="Bob Jones")
    _conversation(db_session, biz.id, alice.id)
    _conversation(db_session, biz.id, bob.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"search": "alice"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["display_name"] == "Alice Smith"
    app.dependency_overrides.clear()


def test_search_matches_phone_number(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    alice = _customer(db_session, biz.id, wa_phone="+15551230000", display_name="Alice")
    bob = _customer(db_session, biz.id, wa_phone="+15559998888", display_name="Bob")
    _conversation(db_session, biz.id, alice.id)
    _conversation(db_session, biz.id, bob.id)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"search": "5551230000"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["wa_phone"] == "+15551230000"
    app.dependency_overrides.clear()


# --- status filtering ----------------------------------------------------


def test_filter_open_returns_only_active_conversations(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    _conversation(db_session, biz.id, cust.id, conv_status="active")
    _conversation(db_session, biz.id, cust.id, conv_status="closed")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"status": "open"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["status"] == "active"
    app.dependency_overrides.clear()


def test_filter_closed_returns_only_closed_conversations(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    _conversation(db_session, biz.id, cust.id, conv_status="active")
    _conversation(db_session, biz.id, cust.id, conv_status="closed")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"status": "closed"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["status"] == "closed"
    app.dependency_overrides.clear()


def test_filter_escalated_returns_only_escalated_conversations(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    _conversation(db_session, biz.id, cust.id, conv_status="active")
    _conversation(db_session, biz.id, cust.id, conv_status="escalated")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"status": "escalated"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["status"] == "escalated"
    app.dependency_overrides.clear()


def test_filter_pending_returns_only_conversations_awaiting_approval(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust_pending = _customer(db_session, biz.id, wa_phone="+10000001")
    cust_clear = _customer(db_session, biz.id, wa_phone="+10000002")
    conv_pending = _conversation(db_session, biz.id, cust_pending.id)
    conv_clear = _conversation(db_session, biz.id, cust_clear.id)
    _message(
        db_session, conv_pending.id, biz.id, direction="outbound", msg_status="pending_approval"
    )
    _message(db_session, conv_clear.id, biz.id, direction="outbound", msg_status="sent")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"status": "pending"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == str(conv_pending.id)
    assert data[0]["has_pending_approval"] is True
    app.dependency_overrides.clear()


def test_has_pending_approval_flag_is_false_without_a_pending_message(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    _message(db_session, conv.id, biz.id, direction="outbound", msg_status="sent")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data[0]["has_pending_approval"] is False
    app.dependency_overrides.clear()


# --- ordering, preview, pagination -----------------------------------------


def test_list_orders_by_most_recent_activity_first(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust1 = _customer(db_session, biz.id, wa_phone="+10000001")
    cust2 = _customer(db_session, biz.id, wa_phone="+10000002")
    older = _conversation(db_session, biz.id, cust1.id, last_message_at=NOW - timedelta(hours=2))
    newer = _conversation(db_session, biz.id, cust2.id, last_message_at=NOW)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    data = resp.json()["data"]
    assert [row["id"] for row in data] == [str(newer.id), str(older.id)]
    app.dependency_overrides.clear()


def test_preview_reflects_the_latest_message_body(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    _message(
        db_session, conv.id, biz.id, body="First message", created_at=NOW - timedelta(minutes=10)
    )
    _message(db_session, conv.id, biz.id, body="Second message", created_at=NOW)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    data = resp.json()["data"]
    assert data[0]["preview"] == "Second message"
    app.dependency_overrides.clear()


def test_pagination_limits_results_and_reports_total(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    for i in range(5):
        cust = _customer(db_session, biz.id, wa_phone=f"+1000000{i}")
        _conversation(db_session, biz.id, cust.id, last_message_at=NOW - timedelta(minutes=i))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"limit": 2, "offset": 0})

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 5, "limit": 2, "offset": 0}

    resp2 = client.get("/api/v1/conversations", headers=_auth(), params={"limit": 2, "offset": 2})
    assert len(resp2.json()["data"]) == 2
    assert resp.json()["data"] != resp2.json()["data"]
    app.dependency_overrides.clear()


# --- channel (Sprint 65 PR 4) --------------------------------------------


def test_list_returns_an_instagram_conversation_with_its_channel(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="IGSID_1")
    _conversation(db_session, biz.id, cust.id, channel="instagram")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["channel"] == "instagram"
    app.dependency_overrides.clear()


def test_get_conversation_exposes_channel_in_detail(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="IGSID_1")
    conv = _conversation(db_session, biz.id, cust.id, channel="instagram")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv.id}", headers=_auth())

    assert resp.json()["data"]["channel"] == "instagram"
    app.dependency_overrides.clear()


def test_list_mixed_channels_orders_by_activity_regardless_of_channel(db_session):
    """Ordering is purely by last_message_at — channel must never affect it
    (the Inbox does not care which provider produced a conversation)."""
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust1 = _customer(db_session, biz.id, wa_phone="+10000001")
    cust2 = _customer(db_session, biz.id, wa_phone="IGSID_2")
    older = _conversation(
        db_session, biz.id, cust1.id, channel="whatsapp", last_message_at=NOW - timedelta(hours=2)
    )
    newer = _conversation(db_session, biz.id, cust2.id, channel="instagram", last_message_at=NOW)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    data = resp.json()["data"]
    assert [row["id"] for row in data] == [str(newer.id), str(older.id)]
    assert [row["channel"] for row in data] == ["instagram", "whatsapp"]
    app.dependency_overrides.clear()


def test_pagination_across_mixed_channels(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    for i in range(3):
        cust = _customer(db_session, biz.id, wa_phone=f"+1000000{i}")
        _conversation(
            db_session,
            biz.id,
            cust.id,
            channel="whatsapp",
            last_message_at=NOW - timedelta(minutes=i),
        )
    for i in range(3):
        cust = _customer(db_session, biz.id, wa_phone=f"IGSID_{i}")
        _conversation(
            db_session,
            biz.id,
            cust.id,
            channel="instagram",
            last_message_at=NOW - timedelta(minutes=10 + i),
        )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    page1 = client.get(
        "/api/v1/conversations", headers=_auth(), params={"limit": 4, "offset": 0}
    ).json()
    page2 = client.get(
        "/api/v1/conversations", headers=_auth(), params={"limit": 4, "offset": 4}
    ).json()

    assert page1["meta"] == {"total": 6, "limit": 4, "offset": 0}
    assert len(page1["data"]) == 4
    assert len(page2["data"]) == 2
    ids_page1 = {row["id"] for row in page1["data"]}
    ids_page2 = {row["id"] for row in page2["data"]}
    assert ids_page1.isdisjoint(ids_page2)  # no overlap/duplication across pages
    app.dependency_overrides.clear()


def test_filter_by_channel_returns_only_that_channel(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    wa_cust = _customer(db_session, biz.id, wa_phone="+10000001")
    ig_cust = _customer(db_session, biz.id, wa_phone="IGSID_1")
    _conversation(db_session, biz.id, wa_cust.id, channel="whatsapp")
    ig_conv = _conversation(db_session, biz.id, ig_cust.id, channel="instagram")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"channel": "instagram"})

    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == str(ig_conv.id)
    app.dependency_overrides.clear()


def test_filter_by_channel_omitted_returns_every_channel(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    wa_cust = _customer(db_session, biz.id, wa_phone="+10000001")
    ig_cust = _customer(db_session, biz.id, wa_phone="IGSID_1")
    _conversation(db_session, biz.id, wa_cust.id, channel="whatsapp")
    _conversation(db_session, biz.id, ig_cust.id, channel="instagram")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth())

    assert len(resp.json()["data"]) == 2
    app.dependency_overrides.clear()


def test_search_by_ig_phone_field_finds_instagram_customers(db_session):
    """Search reuses the existing Customer.wa_phone ILIKE match — no second
    search implementation needed, since Instagram's IGSID is stored in the
    same field WhatsApp's phone number already is."""
    biz, _ = _seed_business(db_session, "A", "user_a")
    ig_cust = _customer(db_session, biz.id, wa_phone="IGSID_998877")
    wa_cust = _customer(db_session, biz.id, wa_phone="+15551230000")
    _conversation(db_session, biz.id, ig_cust.id, channel="instagram")
    _conversation(db_session, biz.id, wa_cust.id, channel="whatsapp")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/conversations", headers=_auth(), params={"search": "998877"})

    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["channel"] == "instagram"
    app.dependency_overrides.clear()


# --- conversation detail ------------------------------------------------


def test_get_conversation_returns_summary_with_customer_and_pending_flag(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001", display_name="Alice")
    conv = _conversation(db_session, biz.id, cust.id)
    _message(db_session, conv.id, biz.id, direction="outbound", msg_status="pending_approval")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv.id}", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == str(conv.id)
    assert data["customer"]["display_name"] == "Alice"
    assert data["has_pending_approval"] is True
    app.dependency_overrides.clear()


# --- message thread -----------------------------------------------------


def test_list_messages_returns_oldest_first(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    first = _message(
        db_session, conv.id, biz.id, body="First", created_at=NOW - timedelta(minutes=5)
    )
    second = _message(db_session, conv.id, biz.id, body="Second", created_at=NOW)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv.id}/messages", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert [m["id"] for m in body["data"]] == [str(first.id), str(second.id)]
    assert body["meta"]["total"] == 2
    app.dependency_overrides.clear()


def test_list_messages_includes_status_for_ai_reply_state(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    _message(
        db_session,
        conv.id,
        biz.id,
        direction="outbound",
        body="Draft reply",
        msg_status="pending_approval",
    )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv.id}/messages", headers=_auth())

    data = resp.json()["data"]
    assert data[0]["status"] == "pending_approval"
    assert data[0]["direction"] == "outbound"
    app.dependency_overrides.clear()


def test_list_messages_unknown_conversation_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(
        "/api/v1/conversations/00000000-0000-0000-0000-000000000000/messages", headers=_auth()
    )
    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_list_messages_pagination_keeps_oldest_first_order(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    for i in range(5):
        _message(
            db_session,
            conv.id,
            biz.id,
            body=f"msg-{i}",
            created_at=NOW - timedelta(minutes=(4 - i)),
        )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    # Most recent 2 of 5 (msg-3, msg-4), still returned oldest-first.
    resp = client.get(
        f"/api/v1/conversations/{conv.id}/messages", headers=_auth(), params={"limit": 2}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert [m["body"] for m in body["data"]] == ["msg-3", "msg-4"]
    assert body["meta"]["total"] == 5
    app.dependency_overrides.clear()


def test_message_thread_exposes_ai_review_metadata(db_session):
    # End-to-end: a pending AI reply's real review metadata reaches the payload.
    biz, _ = _seed_business(db_session, "clinic", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+15551230000")
    conv = _conversation(db_session, biz.id, cust.id)
    db_session.add(
        Message(
            conversation_id=conv.id,
            business_id=biz.id,
            direction="outbound",
            body="Yes — Saturday 9–2.",
            type="text",
            status="pending_approval",
            ai_meta={"model": "x", "retrieved_count": 2},
            created_at=NOW,
        )
    )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/conversations/{conv.id}/messages", headers=_auth())

    assert resp.status_code == 200
    msg = resp.json()["data"][0]
    assert msg["review"]["reply_id"] == msg["id"]
    assert msg["review"]["grounding"] == {"retrieved_count": 2, "sources": []}
    assert msg["review"]["confidence"] is None
    assert msg["review"]["generation_status"] == "complete"
    app.dependency_overrides.clear()
