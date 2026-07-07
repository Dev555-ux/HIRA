"""Tests for the settings API: auth guard, tenant isolation, mode validation."""

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, User


def _seed_business(db, name, clerk_user_id, mode="assisted", phone="PN1"):
    biz = Business(name=name, whatsapp_phone_number_id=phone, mode=mode)
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


def test_get_settings_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/settings")  # no Authorization header
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_get_settings_returns_current_mode(db_session):
    _seed_business(db_session, "A", "user_a", mode="assisted")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/settings", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"mode": "assisted"}
    app.dependency_overrides.clear()


def test_get_settings_is_tenant_scoped(db_session):
    _seed_business(db_session, "A", "user_a", mode="assisted", phone="PN_A")
    _seed_business(db_session, "B", "user_b", mode="autonomous", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/settings", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["mode"] == "assisted"  # not business B's mode
    app.dependency_overrides.clear()


def test_patch_settings_updates_mode(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a", mode="assisted")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch("/api/v1/settings", json={"mode": "autonomous"}, headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == {"mode": "autonomous"}
    db_session.refresh(biz)
    assert biz.mode == "autonomous"
    app.dependency_overrides.clear()


def test_patch_settings_rejects_invalid_mode(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a", mode="assisted")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.patch("/api/v1/settings", json={"mode": "yolo"}, headers=_auth())

    assert resp.status_code == 422
    db_session.refresh(biz)
    assert biz.mode == "assisted"  # untouched
    app.dependency_overrides.clear()


def test_patch_settings_does_not_affect_another_business(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a", mode="assisted", phone="PN_A")
    biz_b, _ = _seed_business(db_session, "B", "user_b", mode="assisted", phone="PN_B")
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch("/api/v1/settings", json={"mode": "autonomous"}, headers=_auth())

    assert resp.status_code == 200
    db_session.refresh(biz_a)
    db_session.refresh(biz_b)
    assert biz_a.mode == "autonomous"
    assert biz_b.mode == "assisted"  # untouched
    app.dependency_overrides.clear()


def test_patch_settings_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.patch("/api/v1/settings", json={"mode": "autonomous"})
    assert resp.status_code == 401
    app.dependency_overrides.clear()
