"""Instagram OAuth 2.0 — Meta's "Instagram API with Facebook Login for
Business" (Sprint 65 PR 2). Classic scope-based Facebook Login (client_id +
scope), not the config_id "Business Login" product app/whatsapp/providers/
embedded_signup_stub.py is blocked on — that one needs a Meta Business Login
configuration only provisioned after Tech Provider approval. This flow uses
a standard OAuth app any Meta Developer account can create today and
exercise in Development Mode against the founder's own test Pages; it works
for real third-party businesses automatically once Meta App Review passes
(TODOS.md ONBOARD-E) — no code change needed then, just Advanced Access.

Endpoints, permission names, and response shapes below come from Meta's own
reference pages (Facebook Login for Business, Graph API user/accounts and
Page references, permission reference pages for instagram_manage_messages/
pages_messaging) — see Sprint 65 PR 2's research notes. Two points those
docs don't hand you directly, verified/decided here instead:
  - Page Access Tokens derived from a long-lived User token do NOT expire on
    a fixed schedule (unlike the User token's own ~60 days) — they stop
    working on specific events (password change, permission revocation).
    So there's no local "expires_at" to check for "needs reconnect"; see
    app/instagram/credentials.py::check_connection_health for the live
    check that substitutes for it.
  - The `/subscribed_apps` webhook-subscription call is a distinct, later
    step (messaging/webhooks PR territory) — not part of connecting.

Mirrors app/calendar/oauth.py's signed-state shape, with two additions
Calendar's own flow doesn't need:
  - Single-use enforcement (app/models.py::InstagramOAuthAttempt) —
    Calendar's verify_state() only checks signature + age, never reuse.
  - Multi-Page discovery — Calendar has exactly one calendar to connect;
    Instagram's callback can find more than one eligible Page, so "return
    structured choices, don't auto-select" needs a bridge from callback to
    a later finalize call (see store_pending_choices/get_pending_attempt).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendar.security import decrypt_token, encrypt_token
from app.core.config import settings
from app.instagram.errors import (
    InstagramAuthError,
    InstagramNotConfiguredError,
    InstagramOAuthStateError,
)
from app.models import InstagramOAuthAttempt

STATE_MAX_AGE_SECONDS = 600

# Permission chain per Meta's own reference pages: instagram_manage_messages
# requires instagram_basic + pages_read_engagement + pages_show_list;
# pages_messaging requires pages_manage_metadata + pages_show_list. Both
# target permissions requested together, so the union of their
# prerequisites is requested up front.
SCOPES = (
    "instagram_basic",
    "instagram_manage_messages",
    "pages_show_list",
    "pages_read_engagement",
    "pages_manage_metadata",
)


def _require_configured() -> None:
    if not (
        settings.instagram_app_id
        and settings.instagram_app_secret
        and settings.instagram_oauth_redirect_uri
    ):
        raise InstagramNotConfiguredError(
            "INSTAGRAM_APP_ID/INSTAGRAM_APP_SECRET/INSTAGRAM_OAUTH_REDIRECT_URI are not set"
        )
    if not settings.calendar_encryption_key:
        raise InstagramNotConfiguredError("CALENDAR_ENCRYPTION_KEY is not set")


def _sign(payload: str) -> str:
    key = settings.calendar_encryption_key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def _new_signed_state(business_id: uuid.UUID) -> str:
    # "instagram:" prefix + a random nonce: the prefix stops a
    # Calendar-issued state (same key, same HMAC scheme, app/calendar/
    # oauth.py) from ever verifying here by accident; the nonce guarantees
    # uniqueness even for two connect attempts by the same business in the
    # same second, which Calendar's own (business_id:timestamp) payload
    # doesn't guarantee — not a problem for Calendar since it never tracks
    # single-use, but this state is also a DB unique key (see
    # verify_and_consume_state).
    payload = f"instagram:{business_id}:{int(time.time())}:{secrets.token_hex(16)}"
    return f"{payload}:{_sign(payload)}"


def _verify_signature_and_age(state: str) -> uuid.UUID:
    try:
        prefix, business_id_str, timestamp_str, _nonce, signature = state.split(":")
    except ValueError as exc:
        raise InstagramOAuthStateError("Malformed state parameter") from exc
    if prefix != "instagram":
        raise InstagramOAuthStateError("Malformed state parameter")

    payload = f"{prefix}:{business_id_str}:{timestamp_str}:{_nonce}"
    if not hmac.compare_digest(_sign(payload), signature):
        raise InstagramOAuthStateError("Invalid state signature")
    if time.time() - int(timestamp_str) > STATE_MAX_AGE_SECONDS:
        raise InstagramOAuthStateError("State parameter expired — please reconnect")
    try:
        return uuid.UUID(business_id_str)
    except ValueError as exc:
        raise InstagramOAuthStateError("Malformed business id in state parameter") from exc


def build_authorization_url(db: Session, business_id: uuid.UUID) -> str:
    """The URL to redirect the dashboard user's browser to for Meta's
    consent screen. Records the issued state in InstagramOAuthAttempt so
    verify_and_consume_state() can later enforce single-use, not just
    signature/age."""
    _require_configured()
    state = _new_signed_state(business_id)
    db.add(
        InstagramOAuthAttempt(
            business_id=business_id,
            state=state,
            expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(seconds=STATE_MAX_AGE_SECONDS),
        )
    )
    db.commit()

    params = {
        "client_id": settings.instagram_app_id,
        "redirect_uri": settings.instagram_oauth_redirect_uri,
        "state": state,
        "response_type": "code",
        "scope": ",".join(SCOPES),
    }
    return f"https://www.facebook.com/{settings.instagram_graph_version}/dialog/oauth?{urlencode(params)}"


def verify_and_consume_state(db: Session, state: str) -> InstagramOAuthAttempt:
    """Full validation: signature + age (forged/expired — same checks
    app/calendar/oauth.py's verify_state() does) plus single-use, the gap
    that function deliberately doesn't cover (see this module's docstring).
    Rejects missing/invalid/expired/reused state in every case. Marks the
    row consumed and returns it (not just the business_id) — the caller may
    still need it to record a pending multi-Page selection."""
    _verify_signature_and_age(state)

    attempt = db.scalars(
        select(InstagramOAuthAttempt).where(InstagramOAuthAttempt.state == state)
    ).first()
    if attempt is None:
        raise InstagramOAuthStateError("Unrecognized state parameter")
    if attempt.consumed_at is not None:
        raise InstagramOAuthStateError("This connection request was already used")
    if attempt.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise InstagramOAuthStateError("State parameter expired — please reconnect")

    attempt.consumed_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return attempt


def _fetch_access_token(client: httpx.Client, params: dict) -> str:
    url = f"https://graph.facebook.com/{settings.instagram_graph_version}/oauth/access_token"
    try:
        resp = client.get(url, params=params)
    except httpx.TransportError as exc:
        raise InstagramAuthError(f"Could not reach Meta's API: {exc}") from exc
    if resp.status_code >= 400:
        raise InstagramAuthError(
            f"Meta rejected the token exchange: {resp.status_code} {resp.text}"
        )
    token = resp.json().get("access_token")
    if not token:
        raise InstagramAuthError("Meta's token exchange response did not include an access token")
    return token


def exchange_code_for_user_token(code: str, *, client: httpx.Client | None = None) -> str:
    """Exchange an authorization code for a short-lived User access token,
    then immediately exchange that for the long-lived version (~60 days;
    see this module's docstring for why Page tokens derived from it don't
    inherit that expiry)."""
    _require_configured()
    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        short_lived = _fetch_access_token(
            client,
            {
                "client_id": settings.instagram_app_id,
                "client_secret": settings.instagram_app_secret,
                "redirect_uri": settings.instagram_oauth_redirect_uri,
                "code": code,
            },
        )
        return _fetch_access_token(
            client,
            {
                "grant_type": "fb_exchange_token",
                "client_id": settings.instagram_app_id,
                "client_secret": settings.instagram_app_secret,
                "fb_exchange_token": short_lived,
            },
        )
    finally:
        if owns_client:
            client.close()


@dataclass(frozen=True)
class InstagramConnectionChoice:
    page_id: str
    page_name: str
    page_access_token: str
    instagram_business_account_id: str
    instagram_username: str | None


def discover_connectable_pages(
    user_access_token: str, *, client: httpx.Client | None = None
) -> list[InstagramConnectionChoice]:
    """Every Page the authorizing user manages that has both a connected
    Instagram professional account and a usable Page access token — a Page
    missing either is silently excluded (nothing valid to connect), not
    surfaced as a broken choice."""
    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        url = f"https://graph.facebook.com/{settings.instagram_graph_version}/me/accounts"
        try:
            resp = client.get(
                url,
                params={
                    "access_token": user_access_token,
                    "fields": "id,name,access_token,instagram_business_account{id,username}",
                },
            )
        except httpx.TransportError as exc:
            raise InstagramAuthError(f"Could not reach Meta's API: {exc}") from exc
        if resp.status_code >= 400:
            raise InstagramAuthError(
                f"Meta rejected the Page discovery request: {resp.status_code} {resp.text}"
            )

        choices = []
        for page in resp.json().get("data", []):
            ig_account = page.get("instagram_business_account")
            page_access_token = page.get("access_token")
            if not ig_account or not ig_account.get("id") or not page_access_token:
                continue
            choices.append(
                InstagramConnectionChoice(
                    page_id=page["id"],
                    page_name=page.get("name", ""),
                    page_access_token=page_access_token,
                    instagram_business_account_id=ig_account["id"],
                    instagram_username=ig_account.get("username"),
                )
            )
        return choices
    finally:
        if owns_client:
            client.close()


def store_pending_choices(
    db: Session, attempt: InstagramOAuthAttempt, user_access_token: str
) -> str:
    """Called when a callback finds more than one eligible Page (Sprint 65
    PR 2: "return structured choices, do not automatically select one").
    Encrypts and holds the User access token against this attempt row so
    `POST /connect/finalize` can re-run discovery for the chosen Page
    without the frontend ever handling a raw Meta access token."""
    attempt.selection_token = secrets.token_urlsafe(32)
    attempt.user_access_token_encrypted = encrypt_token(user_access_token)
    db.commit()
    return attempt.selection_token


def get_pending_attempt(
    db: Session, business_id: uuid.UUID, selection_token: str
) -> InstagramOAuthAttempt | None:
    attempt = db.scalars(
        select(InstagramOAuthAttempt).where(
            InstagramOAuthAttempt.selection_token == selection_token,
            InstagramOAuthAttempt.business_id == business_id,
        )
    ).first()
    if attempt is None or attempt.user_access_token_encrypted is None:
        return None
    if attempt.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        return None
    return attempt


def decrypt_pending_token(attempt: InstagramOAuthAttempt) -> str:
    return decrypt_token(attempt.user_access_token_encrypted)


def consume_pending_attempt(db: Session, attempt: InstagramOAuthAttempt) -> None:
    """One-shot: a finalized selection can't be replayed to finalize again
    (or reused to keep re-listing choices) once it has completed a
    connection."""
    attempt.user_access_token_encrypted = None
    attempt.selection_token = None
    db.commit()
