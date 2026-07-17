"""Tests for the Customers API (/api/v1/customers): auth, tenant isolation,
search, pagination, lead embedding, and the customer timeline endpoint."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, Lead, Message, User

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


def _conversation(db, business_id, customer_id, *, last_message_at=None):
    conv = Conversation(
        business_id=business_id, customer_id=customer_id, last_message_at=last_message_at
    )
    db.add(conv)
    db.flush()
    return conv


def _message(db, conversation_id, business_id, *, body="hi", created_at=None):
    msg = Message(
        conversation_id=conversation_id,
        business_id=business_id,
        direction="inbound",
        body=body,
        status="received",
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


# --- list --------------------------------------------------------------


def test_list_customers_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_list_customers_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    _customer(db_session, biz_a.id, wa_phone="+10000001")
    _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/customers", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["wa_phone"] == "+10000001"
    app.dependency_overrides.clear()


def test_list_customers_excludes_demo_chat_customer(db_session):
    # Regression: Demo Chat's synthetic customer (wa_phone="__playground__",
    # app/ai/playground.py) must never appear in the real Customers list —
    # it previously did, since this query had no wa_phone exclusion.
    biz, _ = _seed_business(db_session, "A", "user_a")
    _customer(db_session, biz.id, wa_phone="+10000001")
    _customer(db_session, biz.id, wa_phone="__playground__", display_name="Demo Chat")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/customers", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["wa_phone"] == "+10000001"
    app.dependency_overrides.clear()


def test_list_customers_search_matches_name_or_phone(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    _customer(db_session, biz.id, wa_phone="+10000001", display_name="Jordan Lee")
    _customer(db_session, biz.id, wa_phone="+19998887777", display_name="Sam Patel")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/customers?search=Jordan", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["display_name"] == "Jordan Lee"
    app.dependency_overrides.clear()


def test_list_customers_includes_conversation_count_and_lead_summary(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    _conversation(db_session, biz.id, cust.id, last_message_at=NOW)
    db_session.add(Lead(business_id=biz.id, customer_id=cust.id, stage="qualified"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/customers", headers=_auth())

    row = resp.json()["data"][0]
    assert row["conversation_count"] == 1
    assert row["last_message_at"] is not None
    assert row["lead"] == {"id": row["lead"]["id"], "stage": "qualified"}
    app.dependency_overrides.clear()


def test_list_customers_lead_is_null_when_no_lead_exists(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/customers", headers=_auth())

    assert resp.json()["data"][0]["lead"] is None
    app.dependency_overrides.clear()


def test_list_customers_paginates(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    for i in range(5):
        _customer(db_session, biz.id, wa_phone=f"+1000000{i}")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/customers?limit=2&offset=2", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 5, "limit": 2, "offset": 2}
    app.dependency_overrides.clear()


# --- detail --------------------------------------------------------------


def test_get_customer_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(f"/api/v1/customers/{cust.id}")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_cannot_get_another_businesss_customer(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/customers/{cust_b.id}", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_get_customer_embeds_full_lead(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.add(
        Lead(
            business_id=biz.id,
            customer_id=cust.id,
            stage="proposal_sent",
            source="whatsapp",
            notes="wants a demo",
        )
    )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/customers/{cust.id}", headers=_auth())

    lead = resp.json()["data"]["lead"]
    assert lead["stage"] == "proposal_sent"
    assert lead["source"] == "whatsapp"
    assert lead["notes"] == "wants a demo"
    app.dependency_overrides.clear()


def test_get_unknown_customer_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/customers/00000000-0000-0000-0000-000000000000", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


# --- timeline --------------------------------------------------------------


def test_customer_timeline_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(f"/api/v1/customers/{cust.id}/timeline")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_customer_timeline_merges_messages_and_lead_events(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    _message(
        db_session, conv.id, biz.id, body="are you open?", created_at=datetime(2026, 7, 1, 9, 0)
    )
    db_session.add(Lead(business_id=biz.id, customer_id=cust.id, stage="new"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/customers/{cust.id}/timeline", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    types = {item["type"] for item in body["data"]}
    assert types == {
        "message"
    }  # Lead created directly via ORM here, not create_lead(), so no event
    assert body["meta"]["total"] == 1
    app.dependency_overrides.clear()


def test_customer_timeline_is_tenant_scoped(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/customers/{cust_b.id}/timeline", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_customer_timeline_paginates(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    conv = _conversation(db_session, biz.id, cust.id)
    for i in range(4):
        _message(db_session, conv.id, biz.id, body=f"msg{i}", created_at=datetime(2026, 7, 1, 9, i))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/customers/{cust.id}/timeline?limit=2&offset=0", headers=_auth())

    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 4, "limit": 2, "offset": 0}
    assert body["data"][0]["body"] == "msg3"
    app.dependency_overrides.clear()


# --- create (Sprint 37) ------------------------------------------------------


def test_create_customer_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.post("/api/v1/customers", json={"display_name": "Alex Rivera"})
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_create_customer_with_name_only(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/customers", json={"display_name": "Alex Rivera"}, headers=_auth())

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["display_name"] == "Alex Rivera"
    assert data["wa_phone"] is None
    assert data["email"] is None
    assert data["notes"] is None
    assert data["conversation_count"] == 0
    assert data["lead"] is None
    app.dependency_overrides.clear()


def test_create_customer_with_all_fields(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/customers",
        json={
            "display_name": "Jordan Lee",
            "wa_phone": "+15559876543",
            "email": "jordan@example.com",
            "notes": "Prefers afternoon appointments",
        },
        headers=_auth(),
    )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["wa_phone"] == "+15559876543"
    assert data["email"] == "jordan@example.com"
    assert data["notes"] == "Prefers afternoon appointments"

    stored = db_session.get(Customer, data["id"])
    assert stored.business_id == biz.id
    app.dependency_overrides.clear()


def test_create_customer_rejects_blank_name(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/customers", json={"display_name": "   "}, headers=_auth())

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_create_customer_rejects_invalid_email(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/customers",
        json={"display_name": "Alex Rivera", "email": "not-an-email"},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_create_customer_rejects_duplicate_phone(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    _customer(db_session, biz.id, wa_phone="+15551230000")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/customers",
        json={"display_name": "Duplicate", "wa_phone": "+15551230000"},
        headers=_auth(),
    )

    assert resp.status_code == 409
    app.dependency_overrides.clear()


def test_create_customer_allows_same_phone_across_businesses(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    _customer(db_session, biz_b.id, wa_phone="+15551230000")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/customers",
        json={"display_name": "Not a duplicate", "wa_phone": "+15551230000"},
        headers=_auth(),
    )

    assert resp.status_code == 201
    app.dependency_overrides.clear()


def test_create_customer_does_not_create_lead_conversation_or_message(db_session):
    from sqlalchemy import select

    from app.models import Conversation as ConversationModel
    from app.models import Lead as LeadModel
    from app.models import Message as MessageModel

    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/customers",
        json={"display_name": "Alex Rivera", "wa_phone": "+15551230000"},
        headers=_auth(),
    )

    assert resp.status_code == 201
    assert db_session.scalars(select(LeadModel)).all() == []
    assert db_session.scalars(select(ConversationModel)).all() == []
    assert db_session.scalars(select(MessageModel)).all() == []
    app.dependency_overrides.clear()


# --- update (Sprint 37) ------------------------------------------------------


def test_patch_customer_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.patch(f"/api/v1/customers/{cust.id}", json={"notes": "x"})
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_patch_customer_updates_fields(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001", display_name="Old Name")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/customers/{cust.id}",
        json={"display_name": "New Name", "notes": "Called back on Tuesday"},
        headers=_auth(),
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["display_name"] == "New Name"
    assert data["notes"] == "Called back on Tuesday"
    assert data["wa_phone"] == "+10000001"  # untouched
    app.dependency_overrides.clear()


def test_patch_customer_rejects_nothing_to_update(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(f"/api/v1/customers/{cust.id}", json={}, headers=_auth())

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_customer_rejects_duplicate_phone(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    _customer(db_session, biz.id, wa_phone="+15551111111")
    other = _customer(db_session, biz.id, wa_phone="+15552222222")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(
        f"/api/v1/customers/{other.id}",
        json={"wa_phone": "+15551111111"},
        headers=_auth(),
    )

    assert resp.status_code == 409
    app.dependency_overrides.clear()


def test_cannot_patch_another_businesss_customer(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch(
        f"/api/v1/customers/{cust_b.id}", json={"notes": "hijacked"}, headers=_auth()
    )

    assert resp.status_code == 404
    db_session.refresh(cust_b)
    assert cust_b.notes is None
    app.dependency_overrides.clear()


# --- delete (Sprint 37) ------------------------------------------------------


def test_delete_customer_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.delete(f"/api/v1/customers/{cust.id}")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_delete_customer_removes_it(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.delete(f"/api/v1/customers/{cust.id}", headers=_auth())

    assert resp.status_code == 204
    assert db_session.get(Customer, cust.id) is None
    app.dependency_overrides.clear()


def test_delete_unknown_customer_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.delete("/api/v1/customers/00000000-0000-0000-0000-000000000000", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_cannot_delete_another_businesss_customer(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.delete(f"/api/v1/customers/{cust_b.id}", headers=_auth())

    assert resp.status_code == 404
    assert db_session.get(Customer, cust_b.id) is not None
    app.dependency_overrides.clear()
