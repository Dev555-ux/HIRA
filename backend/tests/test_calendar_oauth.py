"""Tests for app/calendar/oauth.py: state signing/verification (CSRF/replay
protection on the public callback route) and the authorization-url/code-
exchange entry points (DEC-032)."""

import time
import uuid

import pytest
from cryptography.fernet import Fernet

from app.calendar.oauth import (
    OAuthStateError,
    build_authorization_url,
    exchange_code_for_refresh_token,
    sign_state,
    verify_state,
)
from app.calendar.providers.base import CalendarAuthError, CalendarNotConfiguredError
from app.core.config import settings


@pytest.fixture(autouse=True)
def _calendar_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _configure_google(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "client-id")
    monkeypatch.setattr(settings, "google_client_secret", "client-secret")
    monkeypatch.setattr(settings, "google_oauth_redirect_uri", "http://localhost:8000/callback")


# --- state signing -----------------------------------------------------------


def test_sign_then_verify_state_roundtrips():
    business_id = uuid.uuid4()
    state = sign_state(business_id)

    assert verify_state(state) == business_id


def test_verify_state_rejects_malformed_state():
    with pytest.raises(OAuthStateError):
        verify_state("not-a-valid-state")


def test_verify_state_rejects_tampered_signature():
    business_id = uuid.uuid4()
    state = sign_state(business_id)
    tampered = state[:-1] + ("0" if state[-1] != "0" else "1")

    with pytest.raises(OAuthStateError):
        verify_state(tampered)


def test_verify_state_rejects_expired_state(monkeypatch):
    business_id = uuid.uuid4()
    state = sign_state(business_id)
    real_time = time.time()

    monkeypatch.setattr(time, "time", lambda: real_time + 700)  # past the 600s window

    with pytest.raises(OAuthStateError):
        verify_state(state)


def test_verify_state_rejects_a_different_businesss_forged_id():
    business_id = uuid.uuid4()
    state = sign_state(business_id)
    forged_id = uuid.uuid4()
    _, timestamp, signature = state.split(":")

    with pytest.raises(OAuthStateError):
        verify_state(f"{forged_id}:{timestamp}:{signature}")


# --- authorization URL / code exchange ---------------------------------------


def test_build_authorization_url_requires_google_config(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    with pytest.raises(CalendarNotConfiguredError):
        build_authorization_url(uuid.uuid4())


def test_build_authorization_url_requires_encryption_key(monkeypatch):
    _configure_google(monkeypatch)
    monkeypatch.setattr(settings, "calendar_encryption_key", "")
    with pytest.raises(CalendarNotConfiguredError):
        build_authorization_url(uuid.uuid4())


def test_build_authorization_url_includes_signed_state(monkeypatch):
    _configure_google(monkeypatch)
    business_id = uuid.uuid4()

    url = build_authorization_url(business_id)

    assert "accounts.google.com" in url
    assert "state=" in url


def test_build_authorization_url_does_not_request_pkce(monkeypatch):
    # Regression test: google-auth-oauthlib >=1.x defaults to
    # autogenerate_code_verifier=True, which puts a code_challenge in this URL
    # but the verifier only lives on this Flow instance's Python object — it's
    # gone by the time the callback's separate request builds a new Flow to
    # exchange the code, so Google rejects the exchange with "Missing code
    # verifier". This client already authenticates via client_secret and
    # doesn't need PKCE, so the fix is to turn it off, not to thread the
    # verifier through the callback.
    _configure_google(monkeypatch)

    url = build_authorization_url(uuid.uuid4())

    assert "code_challenge" not in url


def test_exchange_code_requires_google_config(monkeypatch):
    monkeypatch.setattr(settings, "google_client_id", "")
    with pytest.raises(CalendarNotConfiguredError):
        exchange_code_for_refresh_token("some-code")


def test_exchange_code_wraps_failed_exchange_as_calendar_auth_error(monkeypatch):
    _configure_google(monkeypatch)

    class _FakeFlow:
        credentials = None

        def fetch_token(self, code):
            from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

            raise InvalidGrantError("bad code")

    monkeypatch.setattr("app.calendar.oauth._build_flow", lambda: _FakeFlow())

    with pytest.raises(CalendarAuthError):
        exchange_code_for_refresh_token("bad-code")


def test_exchange_code_raises_if_no_refresh_token_returned(monkeypatch):
    _configure_google(monkeypatch)

    class _FakeCredentials:
        refresh_token = None

    class _FakeFlow:
        credentials = _FakeCredentials()

        def fetch_token(self, code):
            return None

    monkeypatch.setattr("app.calendar.oauth._build_flow", lambda: _FakeFlow())

    with pytest.raises(CalendarAuthError):
        exchange_code_for_refresh_token("some-code")


def test_exchange_code_returns_refresh_token_on_success(monkeypatch):
    _configure_google(monkeypatch)

    class _FakeCredentials:
        refresh_token = "a-refresh-token"

    class _FakeFlow:
        credentials = _FakeCredentials()

        def fetch_token(self, code):
            return None

    monkeypatch.setattr("app.calendar.oauth._build_flow", lambda: _FakeFlow())

    assert exchange_code_for_refresh_token("some-code") == "a-refresh-token"
