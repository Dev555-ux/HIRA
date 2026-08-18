"""Tests for app/instagram/oauth.py: signed + single-use state validation
(CSRF/replay protection on the public callback route), token exchange, and
Page discovery (Sprint 65 PR 2)."""

from __future__ import annotations

import time

import httpx
import pytest
from cryptography.fernet import Fernet

from app.instagram.errors import (
    InstagramAuthError,
    InstagramNotConfiguredError,
    InstagramOAuthStateError,
)
from app.instagram.oauth import (
    build_authorization_url,
    consume_pending_attempt,
    discover_connectable_pages,
    exchange_code_for_user_token,
    get_pending_attempt,
    store_pending_choices,
    verify_and_consume_state,
)
from app.core.config import settings
from app.models import Business


@pytest.fixture(autouse=True)
def _configured(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "instagram_app_id", "app-id")
    monkeypatch.setattr(settings, "instagram_app_secret", "app-secret")
    monkeypatch.setattr(settings, "instagram_oauth_redirect_uri", "http://localhost:8000/callback")


def _seed_business(db_session) -> Business:
    biz = Business(name="A")
    db_session.add(biz)
    db_session.commit()
    return biz


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# --- state signing / single-use ------------------------------------------


def test_build_then_verify_state_roundtrips(db_session):
    biz = _seed_business(db_session)
    url = build_authorization_url(db_session, biz.id)

    state = url.split("state=")[1].split("&")[0]
    from urllib.parse import unquote

    attempt = verify_and_consume_state(db_session, unquote(state))
    assert attempt.business_id == biz.id


def test_verify_state_rejects_malformed_state(db_session):
    with pytest.raises(InstagramOAuthStateError):
        verify_and_consume_state(db_session, "not-a-valid-state")


def test_verify_state_rejects_a_calendar_issued_state(db_session):
    """Same key, same HMAC scheme as app/calendar/oauth.py — the payload
    prefix is what stops a Calendar-issued state from verifying here."""
    from app.calendar.oauth import sign_state

    biz = _seed_business(db_session)
    calendar_state = sign_state(biz.id)

    with pytest.raises(InstagramOAuthStateError):
        verify_and_consume_state(db_session, calendar_state)


def test_verify_state_rejects_tampered_signature(db_session):
    biz = _seed_business(db_session)
    url = build_authorization_url(db_session, biz.id)
    from urllib.parse import unquote

    state = unquote(url.split("state=")[1].split("&")[0])
    tampered = state[:-1] + ("0" if state[-1] != "0" else "1")

    with pytest.raises(InstagramOAuthStateError):
        verify_and_consume_state(db_session, tampered)


def test_verify_state_rejects_expired_state(db_session, monkeypatch):
    biz = _seed_business(db_session)
    real_time = time.time()
    monkeypatch.setattr(time, "time", lambda: real_time - 700)
    url = build_authorization_url(db_session, biz.id)
    monkeypatch.setattr(time, "time", lambda: real_time)
    from urllib.parse import unquote

    state = unquote(url.split("state=")[1].split("&")[0])

    with pytest.raises(InstagramOAuthStateError):
        verify_and_consume_state(db_session, state)


def test_verify_state_rejects_reused_state(db_session):
    """The gap app/calendar/oauth.py's own verify_state() doesn't cover —
    Sprint 65 PR 2 explicitly requires rejecting a reused state."""
    biz = _seed_business(db_session)
    url = build_authorization_url(db_session, biz.id)
    from urllib.parse import unquote

    state = unquote(url.split("state=")[1].split("&")[0])

    verify_and_consume_state(db_session, state)
    with pytest.raises(InstagramOAuthStateError):
        verify_and_consume_state(db_session, state)


def test_verify_state_rejects_unrecognized_state(db_session):
    """Well-formed and correctly signed, but never issued/persisted (e.g. a
    forged business_id) — signature alone isn't enough without the DB
    record, since forging a state for a HMAC key you don't have is only
    prevented by the signature holding at all."""
    biz = _seed_business(db_session)
    build_authorization_url(db_session, biz.id)  # issues a real, different state
    from app.instagram.oauth import _new_signed_state

    forged_but_signed = _new_signed_state(biz.id)  # signed correctly, never stored
    with pytest.raises(InstagramOAuthStateError):
        verify_and_consume_state(db_session, forged_but_signed)


def test_build_authorization_url_raises_when_not_configured(db_session, monkeypatch):
    monkeypatch.setattr(settings, "instagram_app_id", "")
    biz = _seed_business(db_session)
    with pytest.raises(InstagramNotConfiguredError):
        build_authorization_url(db_session, biz.id)


def test_authorization_url_contains_expected_params(db_session):
    biz = _seed_business(db_session)
    url = build_authorization_url(db_session, biz.id)

    assert url.startswith("https://www.facebook.com/")
    assert "dialog/oauth" in url
    assert "client_id=app-id" in url
    assert "instagram_manage_messages" in url


# --- token exchange --------------------------------------------------------


def test_exchange_code_for_user_token_does_two_hop_exchange():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(request.url.params))
        if "fb_exchange_token" in request.url.params:
            return httpx.Response(200, json={"access_token": "long-lived-token"})
        return httpx.Response(200, json={"access_token": "short-lived-token"})

    client = _mock_transport(handler)
    token = exchange_code_for_user_token("auth-code", client=client)

    assert token == "long-lived-token"
    assert len(calls) == 2
    assert calls[0]["code"] == "auth-code"
    assert calls[1]["fb_exchange_token"] == "short-lived-token"


def test_exchange_code_for_user_token_raises_on_meta_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "bad code"}})

    client = _mock_transport(handler)
    with pytest.raises(InstagramAuthError):
        exchange_code_for_user_token("bad-code", client=client)


# --- Page discovery ----------------------------------------------------------


def test_discover_connectable_pages_filters_pages_without_ig_account():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "page-1",
                        "name": "Page One",
                        "access_token": "page-token-1",
                        "instagram_business_account": {"id": "ig-1", "username": "biz_one"},
                    },
                    {"id": "page-2", "name": "Page Two", "access_token": "page-token-2"},
                ]
            },
        )

    client = _mock_transport(handler)
    choices = discover_connectable_pages("user-token", client=client)

    assert len(choices) == 1
    assert choices[0].page_id == "page-1"
    assert choices[0].instagram_business_account_id == "ig-1"
    assert choices[0].instagram_username == "biz_one"


def test_discover_connectable_pages_raises_on_meta_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad token"}})

    client = _mock_transport(handler)
    with pytest.raises(InstagramAuthError):
        discover_connectable_pages("user-token", client=client)


# --- pending multi-choice bridge --------------------------------------------


def test_pending_choices_roundtrip(db_session):
    biz = _seed_business(db_session)
    url = build_authorization_url(db_session, biz.id)
    from urllib.parse import unquote

    state = unquote(url.split("state=")[1].split("&")[0])
    attempt = verify_and_consume_state(db_session, state)

    selection_token = store_pending_choices(db_session, attempt, "a-user-access-token")

    fetched = get_pending_attempt(db_session, biz.id, selection_token)
    assert fetched is not None
    from app.instagram.oauth import decrypt_pending_token

    assert decrypt_pending_token(fetched) == "a-user-access-token"

    consume_pending_attempt(db_session, fetched)
    assert get_pending_attempt(db_session, biz.id, selection_token) is None


def test_get_pending_attempt_scoped_to_business(db_session):
    biz_a = _seed_business(db_session)
    biz_b = Business(name="B")
    db_session.add(biz_b)
    db_session.commit()

    url = build_authorization_url(db_session, biz_a.id)
    from urllib.parse import unquote

    state = unquote(url.split("state=")[1].split("&")[0])
    attempt = verify_and_consume_state(db_session, state)
    selection_token = store_pending_choices(db_session, attempt, "token")

    assert get_pending_attempt(db_session, biz_b.id, selection_token) is None
    assert get_pending_attempt(db_session, biz_a.id, selection_token) is not None


def test_get_pending_attempt_unknown_token_returns_none(db_session):
    biz = _seed_business(db_session)
    assert get_pending_attempt(db_session, biz.id, "nonexistent") is None
