"""Tests for the Instagram API (/api/v1/instagram): auth, OAuth connect/
callback, the multi-Page choose/finalize bridge, status, and disconnect
(Sprint 65 PR 2)."""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.instagram import credentials as instagram_credentials
from app.instagram import oauth
from app.instagram.oauth import InstagramConnectionChoice
from app.main import app
from app.models import Business, User


def _seed_business(db, name, clerk_user_id):
    biz = Business(name=name)
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


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "instagram_app_id", "app-id")
    monkeypatch.setattr(settings, "instagram_app_secret", "app-secret")
    monkeypatch.setattr(
        settings,
        "instagram_oauth_redirect_uri",
        "http://localhost:8000/api/v1/instagram/oauth/callback",
    )


@pytest.fixture(autouse=True)
def _clear_overrides():
    yield
    app.dependency_overrides.clear()


def _get_state(url: str) -> str:
    return unquote(url.split("state=")[1].split("&")[0])


# --- oauth/connect -----------------------------------------------------------


def test_oauth_connect_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/instagram/oauth/connect")
    assert resp.status_code == 401


def test_oauth_connect_returns_authorization_url(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/instagram/oauth/connect", headers=_auth())

    assert resp.status_code == 200
    assert "facebook.com" in resp.json()["data"]["authorization_url"]


def test_oauth_connect_returns_503_when_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "instagram_app_id", "")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/instagram/oauth/connect", headers=_auth())

    assert resp.status_code == 503
    detail = resp.json()["detail"]
    assert "INSTAGRAM_APP_ID" not in detail  # never leak env var names to the client


# --- oauth/callback (public — no Clerk session) ------------------------------


def test_oauth_callback_single_choice_stores_credentials_and_redirects(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session

    url = oauth.build_authorization_url(db_session, biz.id)
    state = _get_state(url)

    monkeypatch.setattr(oauth, "exchange_code_for_user_token", lambda code: "user-token")
    monkeypatch.setattr(
        oauth,
        "discover_connectable_pages",
        lambda token: [
            InstagramConnectionChoice("page-1", "Page One", "page-token", "ig-1", "biz_one")
        ],
    )

    client = TestClient(app)
    resp = client.get(
        f"/api/v1/instagram/oauth/callback?code=abc&state={state}", follow_redirects=False
    )

    assert resp.status_code in (302, 307)
    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["instagram"] == ["connected"]
    stored = instagram_credentials.get_stored_credential(db_session, biz.id)
    assert stored is not None
    assert stored.instagram_business_account_id == "ig-1"


def test_oauth_callback_multiple_choices_redirects_to_choose(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session

    url = oauth.build_authorization_url(db_session, biz.id)
    state = _get_state(url)

    monkeypatch.setattr(oauth, "exchange_code_for_user_token", lambda code: "user-token")
    monkeypatch.setattr(
        oauth,
        "discover_connectable_pages",
        lambda token: [
            InstagramConnectionChoice("page-1", "Page One", "tok-1", "ig-1", "biz_one"),
            InstagramConnectionChoice("page-2", "Page Two", "tok-2", "ig-2", "biz_two"),
        ],
    )

    client = TestClient(app)
    resp = client.get(
        f"/api/v1/instagram/oauth/callback?code=abc&state={state}", follow_redirects=False
    )

    location = urlparse(resp.headers["location"])
    assert parse_qs(location.query)["instagram"] == ["choose"]
    assert "selection_token" in parse_qs(location.query)
    # Nothing is stored yet — "do not automatically select one".
    assert instagram_credentials.get_stored_credential(db_session, biz.id) is None


def test_oauth_callback_redirects_with_error_on_meta_error_param(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(
        "/api/v1/instagram/oauth/callback?error=access_denied", follow_redirects=False
    )
    assert parse_qs(urlparse(resp.headers["location"]).query)["instagram"] == ["error"]


def test_oauth_callback_redirects_with_error_on_missing_code(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/instagram/oauth/callback?state=whatever", follow_redirects=False)
    assert parse_qs(urlparse(resp.headers["location"]).query)["instagram"] == ["error"]


def test_oauth_callback_redirects_with_error_on_invalid_state(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get(
        "/api/v1/instagram/oauth/callback?code=abc&state=forged", follow_redirects=False
    )
    assert parse_qs(urlparse(resp.headers["location"]).query)["instagram"] == ["error"]


def test_oauth_callback_redirects_with_error_on_reused_state(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    url = oauth.build_authorization_url(db_session, biz.id)
    state = _get_state(url)

    monkeypatch.setattr(oauth, "exchange_code_for_user_token", lambda code: "user-token")
    monkeypatch.setattr(
        oauth,
        "discover_connectable_pages",
        lambda token: [InstagramConnectionChoice("page-1", "Page One", "tok", "ig-1", "biz_one")],
    )

    client = TestClient(app)
    first = client.get(
        f"/api/v1/instagram/oauth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert parse_qs(urlparse(first.headers["location"]).query)["instagram"] == ["connected"]

    second = client.get(
        f"/api/v1/instagram/oauth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert parse_qs(urlparse(second.headers["location"]).query)["instagram"] == ["error"]


def test_oauth_callback_redirects_with_error_when_no_eligible_account(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    url = oauth.build_authorization_url(db_session, biz.id)
    state = _get_state(url)

    monkeypatch.setattr(oauth, "exchange_code_for_user_token", lambda code: "user-token")
    monkeypatch.setattr(oauth, "discover_connectable_pages", lambda token: [])

    client = TestClient(app)
    resp = client.get(
        f"/api/v1/instagram/oauth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert parse_qs(urlparse(resp.headers["location"]).query)["instagram"] == ["error"]


def test_oauth_callback_redirects_with_error_when_account_already_connected(
    db_session, monkeypatch
):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    db_session.commit()
    instagram_credentials.store_credentials(
        db_session,
        biz_a.id,
        page_id="page-1",
        page_access_token="tok",
        instagram_business_account_id="shared-ig",
        instagram_username="taken",
    )

    app.dependency_overrides[get_db] = lambda: db_session
    url = oauth.build_authorization_url(db_session, biz_b.id)
    state = _get_state(url)

    monkeypatch.setattr(oauth, "exchange_code_for_user_token", lambda code: "user-token")
    monkeypatch.setattr(
        oauth,
        "discover_connectable_pages",
        lambda token: [
            InstagramConnectionChoice("page-2", "Page Two", "tok-2", "shared-ig", "taken")
        ],
    )

    client = TestClient(app)
    resp = client.get(
        f"/api/v1/instagram/oauth/callback?code=abc&state={state}", follow_redirects=False
    )
    assert parse_qs(urlparse(resp.headers["location"]).query)["instagram"] == ["error"]
    # biz_a's connection must be untouched.
    assert (
        instagram_credentials.get_stored_credential(
            db_session, biz_a.id
        ).instagram_business_account_id
        == "shared-ig"
    )


# --- choices / finalize -------------------------------------------------------


def test_connect_choices_and_finalize_completes_connection(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()

    app.dependency_overrides[get_db] = lambda: db_session
    from app.models import InstagramOAuthAttempt as Attempt
    from datetime import datetime, timedelta, timezone

    attempt = Attempt(
        business_id=biz.id,
        state="already-consumed-state",
        consumed_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10),
    )
    db_session.add(attempt)
    db_session.commit()
    selection_token = oauth.store_pending_choices(db_session, attempt, "user-token")

    choices = [
        InstagramConnectionChoice("page-1", "Page One", "tok-1", "ig-1", "biz_one"),
        InstagramConnectionChoice("page-2", "Page Two", "tok-2", "ig-2", "biz_two"),
    ]
    monkeypatch.setattr(oauth, "discover_connectable_pages", lambda token: choices)

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    list_resp = client.get(
        f"/api/v1/instagram/connect/choices?selection_token={selection_token}", headers=_auth()
    )
    assert list_resp.status_code == 200
    returned = list_resp.json()["data"]["choices"]
    assert {c["page_id"] for c in returned} == {"page-1", "page-2"}

    finalize_resp = client.post(
        "/api/v1/instagram/connect/finalize",
        json={"selection_token": selection_token, "page_id": "page-2"},
        headers=_auth(),
    )
    assert finalize_resp.status_code == 200
    assert finalize_resp.json()["data"]["connected"] is True

    stored = instagram_credentials.get_stored_credential(db_session, biz.id)
    assert stored.instagram_business_account_id == "ig-2"

    # The selection token is single-use — a second finalize must 404.
    replay = client.post(
        "/api/v1/instagram/connect/finalize",
        json={"selection_token": selection_token, "page_id": "page-2"},
        headers=_auth(),
    )
    assert replay.status_code == 404


def test_connect_choices_unknown_token_returns_404(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/instagram/connect/choices?selection_token=nope", headers=_auth())
    assert resp.status_code == 404


def test_finalize_rejects_a_page_id_not_in_choices(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    from app.models import InstagramOAuthAttempt as Attempt
    from datetime import datetime, timedelta, timezone

    attempt = Attempt(
        business_id=biz.id,
        state="s",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=10),
    )
    db_session.add(attempt)
    db_session.commit()
    selection_token = oauth.store_pending_choices(db_session, attempt, "user-token")

    monkeypatch.setattr(
        oauth,
        "discover_connectable_pages",
        lambda token: [InstagramConnectionChoice("page-1", "Page One", "tok", "ig-1", "u")],
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/instagram/connect/finalize",
        json={"selection_token": selection_token, "page_id": "not-a-real-page"},
        headers=_auth(),
    )
    assert resp.status_code == 422


# --- status / disconnect ------------------------------------------------------


def test_get_status_not_connected(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/instagram/status", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["data"] == {
        "connected": False,
        "status": "disconnected",
        "instagram_username": None,
    }


def test_get_status_connected_runs_live_health_check(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    instagram_credentials.store_credentials(
        db_session,
        biz.id,
        page_id="page-1",
        page_access_token="tok",
        instagram_business_account_id="ig-1",
        instagram_username="biz_one",
    )

    monkeypatch.setattr(
        instagram_credentials, "check_connection_health", lambda credential, **kw: "needs_reconnect"
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/instagram/status", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "needs_reconnect"
    assert resp.json()["data"]["connected"] is False

    # The live result is persisted, not just returned once.
    stored = instagram_credentials.get_stored_credential(db_session, biz.id)
    assert stored.connection_status == "needs_reconnect"


def test_get_status_falls_back_to_last_known_on_network_failure(db_session, monkeypatch):
    from app.instagram.errors import InstagramAuthError

    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    instagram_credentials.store_credentials(
        db_session,
        biz.id,
        page_id="page-1",
        page_access_token="tok",
        instagram_business_account_id="ig-1",
        instagram_username="biz_one",
    )

    def _raise(credential, **kw):
        raise InstagramAuthError("network down")

    monkeypatch.setattr(instagram_credentials, "check_connection_health", _raise)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.get("/api/v1/instagram/status", headers=_auth())
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "connected"  # last-known, not a hard failure


def test_disconnect_removes_credential(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    instagram_credentials.store_credentials(
        db_session,
        biz.id,
        page_id="page-1",
        page_access_token="tok",
        instagram_business_account_id="ig-1",
        instagram_username="biz_one",
    )
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.delete("/api/v1/instagram/disconnect", headers=_auth())
    assert resp.status_code == 204
    assert instagram_credentials.get_stored_credential(db_session, biz.id) is None


def test_disconnect_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.delete("/api/v1/instagram/disconnect")
    assert resp.status_code == 401
