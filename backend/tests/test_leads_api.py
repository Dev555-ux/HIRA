"""Tests for the Leads API (/api/v1/leads): auth, tenant isolation, CRUD,
search/stage filtering, pagination, and validation."""

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, Customer, Lead, User


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


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


# --- create --------------------------------------------------------------


def test_create_lead_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.post("/api/v1/leads", json={"customer_id": str(cust.id)})
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_create_lead_defaults_to_new_stage(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001", display_name="Jordan")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/leads", json={"customer_id": str(cust.id)}, headers=_auth())

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["stage"] == "new"
    assert data["customer"]["display_name"] == "Jordan"
    app.dependency_overrides.clear()


def test_create_lead_with_full_payload(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": str(cust.id),
            "stage": "qualified",
            "source": "referral",
            "estimated_value": 2500.0,
            "notes": "Wants a quote",
            "next_follow_up_at": "2026-08-01T10:00:00",
        },
        headers=_auth(),
    )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["stage"] == "qualified"
    assert data["source"] == "referral"
    assert data["estimated_value"] == 2500.0
    assert data["notes"] == "Wants a quote"
    app.dependency_overrides.clear()


def test_create_lead_rejects_invalid_stage(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/leads",
        json={"customer_id": str(cust.id), "stage": "bogus_stage"},
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_create_lead_for_unknown_customer_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/leads",
        json={"customer_id": "00000000-0000-0000-0000-000000000000"},
        headers=_auth(),
    )

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_create_lead_for_another_businesss_customer_is_404(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/leads", json={"customer_id": str(cust_b.id)}, headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_create_duplicate_lead_is_409(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client.post("/api/v1/leads", json={"customer_id": str(cust.id)}, headers=_auth())

    resp = client.post("/api/v1/leads", json={"customer_id": str(cust.id)}, headers=_auth())

    assert resp.status_code == 409
    app.dependency_overrides.clear()


def test_create_lead_rejects_invalid_assignee(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/leads",
        json={
            "customer_id": str(cust.id),
            "assigned_to": "00000000-0000-0000-0000-000000000000",
        },
        headers=_auth(),
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


# --- list ------------------------------------------------------------------


def test_list_leads_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_a = _customer(db_session, biz_a.id, wa_phone="+10000001")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    db_session.add(Lead(business_id=biz_a.id, customer_id=cust_a.id, stage="new"))
    db_session.add(Lead(business_id=biz_b.id, customer_id=cust_b.id, stage="new"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/leads", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["wa_phone"] == "+10000001"
    app.dependency_overrides.clear()


def test_list_leads_filters_by_stage(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust1 = _customer(db_session, biz.id, wa_phone="+10000001")
    cust2 = _customer(db_session, biz.id, wa_phone="+10000002")
    db_session.add(Lead(business_id=biz.id, customer_id=cust1.id, stage="won"))
    db_session.add(Lead(business_id=biz.id, customer_id=cust2.id, stage="new"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/leads?stage=won", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["stage"] == "won"
    app.dependency_overrides.clear()


def test_list_leads_search_matches_customer_name_or_phone(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust1 = _customer(db_session, biz.id, wa_phone="+10000001", display_name="Jordan Lee")
    cust2 = _customer(db_session, biz.id, wa_phone="+19998887777", display_name="Sam Patel")
    db_session.add(Lead(business_id=biz.id, customer_id=cust1.id))
    db_session.add(Lead(business_id=biz.id, customer_id=cust2.id))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/leads?search=Jordan", headers=_auth())

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["customer"]["display_name"] == "Jordan Lee"
    app.dependency_overrides.clear()


def test_list_leads_paginates(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    for i in range(5):
        cust = _customer(db_session, biz.id, wa_phone=f"+1000000{i}")
        db_session.add(Lead(business_id=biz.id, customer_id=cust.id))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/leads?limit=2&offset=0", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 5, "limit": 2, "offset": 0}
    app.dependency_overrides.clear()


# --- get / patch / delete ---------------------------------------------------


def test_get_lead_requires_authentication(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    lead = Lead(business_id=biz.id, customer_id=cust.id)
    db_session.add(lead)
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(f"/api/v1/leads/{lead.id}")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_cannot_get_another_businesss_lead(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    lead_b = Lead(business_id=biz_b.id, customer_id=cust_b.id)
    db_session.add(lead_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get(f"/api/v1/leads/{lead_b.id}", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()


def test_patch_lead_updates_stage(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    lead = Lead(business_id=biz.id, customer_id=cust.id, stage="new")
    db_session.add(lead)
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(f"/api/v1/leads/{lead.id}", json={"stage": "negotiation"}, headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["stage"] == "negotiation"
    app.dependency_overrides.clear()


def test_patch_lead_can_clear_notes(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    lead = Lead(business_id=biz.id, customer_id=cust.id, notes="old note")
    db_session.add(lead)
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(f"/api/v1/leads/{lead.id}", json={"notes": None}, headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["notes"] is None
    app.dependency_overrides.clear()


def test_patch_lead_rejects_empty_payload(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    lead = Lead(business_id=biz.id, customer_id=cust.id)
    db_session.add(lead)
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(f"/api/v1/leads/{lead.id}", json={}, headers=_auth())

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_patch_lead_rejects_invalid_stage(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    lead = Lead(business_id=biz.id, customer_id=cust.id)
    db_session.add(lead)
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch(f"/api/v1/leads/{lead.id}", json={"stage": "not_a_stage"}, headers=_auth())

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_cannot_patch_another_businesss_lead(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    lead_b = Lead(business_id=biz_b.id, customer_id=cust_b.id, stage="new")
    db_session.add(lead_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch(f"/api/v1/leads/{lead_b.id}", json={"stage": "won"}, headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(lead_b)
    assert lead_b.stage == "new"
    app.dependency_overrides.clear()


def test_delete_lead(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    cust = _customer(db_session, biz.id, wa_phone="+10000001")
    lead = Lead(business_id=biz.id, customer_id=cust.id)
    db_session.add(lead)
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.delete(f"/api/v1/leads/{lead.id}", headers=_auth())

    assert resp.status_code == 204
    assert db_session.get(Lead, lead.id) is None
    app.dependency_overrides.clear()


def test_cannot_delete_another_businesss_lead(db_session):
    _seed_business(db_session, "A", "user_a", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", phone="PN_B")
    cust_b = _customer(db_session, biz_b.id, wa_phone="+10000002")
    lead_b = Lead(business_id=biz_b.id, customer_id=cust_b.id)
    db_session.add(lead_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.delete(f"/api/v1/leads/{lead_b.id}", headers=_auth())

    assert resp.status_code == 404
    assert db_session.get(Lead, lead_b.id) is not None
    app.dependency_overrides.clear()


def test_delete_unknown_lead_is_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.delete("/api/v1/leads/00000000-0000-0000-0000-000000000000", headers=_auth())

    assert resp.status_code == 404
    app.dependency_overrides.clear()
