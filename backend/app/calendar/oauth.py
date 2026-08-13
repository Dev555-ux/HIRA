"""Google OAuth 2.0 authorization-code flow (DEC-032).

Two entry points: `build_authorization_url()` starts the flow (called from an
authenticated dashboard request); `exchange_code_for_refresh_token()`
completes it (called from Google's redirect to the public callback route,
which has no Clerk session — the signed `state` param is what ties the
callback back to a business and guards against a forged/CSRF callback).

Uses the official `google-auth-oauthlib` `Flow`, matching DEC-032's choice
over hand-rolling token exchange.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid

from google.auth.exceptions import GoogleAuthError
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import OAuth2Error

from app.calendar.providers.base import CalendarAuthError, CalendarNotConfiguredError
from app.core.config import settings

SCOPES = ["https://www.googleapis.com/auth/calendar"]
STATE_MAX_AGE_SECONDS = 600


class OAuthStateError(Exception):
    """The `state` param is missing, malformed, forged, or expired."""


def _require_configured() -> None:
    if not (
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_oauth_redirect_uri
    ):
        raise CalendarNotConfiguredError(
            "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/GOOGLE_OAUTH_REDIRECT_URI are not set"
        )
    if not settings.calendar_encryption_key:
        raise CalendarNotConfiguredError("CALENDAR_ENCRYPTION_KEY is not set")


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_oauth_redirect_uri],
        }
    }


def _build_flow() -> Flow:
    # autogenerate_code_verifier=False: this is a confidential server-side
    # client (already authenticated via client_secret), and build_authorization_url
    # / exchange_code_for_refresh_token build separate Flow instances across two
    # different HTTP requests — a PKCE verifier generated in one has no way to
    # reach the other, so Google's token endpoint rejects the exchange with
    # "Missing code verifier" if PKCE is left on.
    return Flow.from_client_config(
        _client_config(),
        scopes=SCOPES,
        redirect_uri=settings.google_oauth_redirect_uri,
        autogenerate_code_verifier=False,
    )


def _sign(payload: str) -> str:
    key = settings.calendar_encryption_key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def sign_state(business_id: uuid.UUID) -> str:
    payload = f"{business_id}:{int(time.time())}"
    return f"{payload}:{_sign(payload)}"


def verify_state(state: str) -> uuid.UUID:
    """Recover the business_id a `state` param was signed for.

    Raises OAuthStateError if the state is malformed, forged, or older than
    STATE_MAX_AGE_SECONDS (replay/CSRF protection on the public callback route).
    """
    try:
        business_id_str, timestamp_str, signature = state.split(":")
    except ValueError as exc:
        raise OAuthStateError("Malformed state parameter") from exc

    expected = _sign(f"{business_id_str}:{timestamp_str}")
    if not hmac.compare_digest(expected, signature):
        raise OAuthStateError("Invalid state signature")
    if time.time() - int(timestamp_str) > STATE_MAX_AGE_SECONDS:
        raise OAuthStateError("State parameter expired — please reconnect")
    try:
        return uuid.UUID(business_id_str)
    except ValueError as exc:
        raise OAuthStateError("Malformed business id in state parameter") from exc


def build_authorization_url(business_id: uuid.UUID) -> str:
    """The URL to redirect the dashboard user to for Google's consent screen."""
    _require_configured()
    authorization_url, _ = _build_flow().authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",  # forces a refresh_token even on a repeat connect
        state=sign_state(business_id),
    )
    return authorization_url


def exchange_code_for_refresh_token(code: str) -> str:
    """Exchange an authorization code (from the callback) for a refresh token.

    Raises CalendarNotConfiguredError if OAuth isn't configured, or
    CalendarAuthError if the exchange itself fails (bad/expired/reused code).
    """
    _require_configured()
    flow = _build_flow()
    try:
        flow.fetch_token(code=code)
    except (OAuth2Error, GoogleAuthError) as exc:
        raise CalendarAuthError(f"Failed to exchange authorization code: {exc}") from exc

    refresh_token = flow.credentials.refresh_token
    if not refresh_token:
        raise CalendarAuthError(
            "Google did not return a refresh token for this authorization — "
            "please reconnect (this can happen if consent wasn't re-prompted)"
        )
    return refresh_token
