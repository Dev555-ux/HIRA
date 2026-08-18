"""Manages a business's own connected Instagram credentials (Sprint 65 PR 2)
— store on connect/reconnect, remove on disconnect, live-check on demand —
mirroring app/whatsapp/credentials.py's shape for WhatsAppCredential.

Reuses app.calendar.security's Fernet wrapper directly (same
CALENDAR_ENCRYPTION_KEY every other domain's secrets already use) rather
than adding a third copy of the same two-function encrypt/decrypt wrapper
app/whatsapp/security.py duplicates — Sprint 65 PR 2 explicitly calls out
not duplicating encryption logic.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.calendar.security import decrypt_token, encrypt_token
from app.core.config import settings
from app.instagram.errors import InstagramAuthError, InstagramDuplicateConnectionError
from app.models import InstagramCredential

CONNECTED = "connected"
NEEDS_RECONNECT = "needs_reconnect"
INVALID_CREDENTIALS = "invalid_credentials"
PERMISSION_REVOKED = "permission_revoked"


def store_credentials(
    db: Session,
    business_id: uuid.UUID,
    *,
    page_id: str,
    page_access_token: str,
    instagram_business_account_id: str,
    instagram_username: str | None,
) -> InstagramCredential:
    """Create-or-replace this business's stored Instagram connection
    (connect and reconnect share this path — both go through the same
    idempotent write, same as WhatsAppCredential's store_credentials).

    `uq_instagram_credentials_ig_account_id` (app/models.py) stops a
    *different* business claiming an IG account already connected
    elsewhere; caught here as a clear InstagramDuplicateConnectionError, not
    a raw IntegrityError leaking to a caller."""
    existing = get_stored_credential(db, business_id)
    encrypted_token = encrypt_token(page_access_token)

    if existing is not None:
        existing.page_id = page_id
        existing.page_access_token_encrypted = encrypted_token
        existing.instagram_business_account_id = instagram_business_account_id
        existing.instagram_username = instagram_username
        existing.connection_status = CONNECTED
    else:
        existing = InstagramCredential(
            business_id=business_id,
            page_id=page_id,
            page_access_token_encrypted=encrypted_token,
            instagram_business_account_id=instagram_business_account_id,
            instagram_username=instagram_username,
            connection_status=CONNECTED,
        )
        db.add(existing)

    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise InstagramDuplicateConnectionError(
            "This Instagram account is already connected to a different business."
        ) from exc

    db.commit()
    db.refresh(existing)
    return existing


def get_stored_credential(db: Session, business_id: uuid.UUID) -> InstagramCredential | None:
    return db.scalars(
        select(InstagramCredential).where(InstagramCredential.business_id == business_id)
    ).first()


def disconnect(db: Session, business_id: uuid.UUID) -> bool:
    """Removes only the stored connection. Never touches Message, Lead, or
    any other customer data — this table has no relation to any of it
    (Sprint 65 PR 2: disconnect must never delete customer data). Returns
    False if nothing was connected."""
    existing = get_stored_credential(db, business_id)
    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return True


def get_page_access_token(credential: InstagramCredential) -> str:
    return decrypt_token(credential.page_access_token_encrypted)


def check_connection_health(
    credential: InstagramCredential, *, client: httpx.Client | None = None
) -> str:
    """One live, cheap Graph API call proving the stored Page access token
    still works — the only way to genuinely distinguish "connected" from
    "needs reconnect"/"invalid credentials"/"permission revoked" without a
    background polling job this PR doesn't add. There's no local expiry
    check that could substitute for this: Page access tokens don't expire on
    a schedule (see app/instagram/oauth.py's module docstring), they just
    stop working on specific Meta-side events.

    Classification is best-effort from Meta's OAuthException error codes:
    code 190 ("Invalid OAuth access token", any subcode) means the token
    itself no longer works; code 10 or a "permission" mention in the error
    message means a previously-granted permission was revoked; anything
    else 4xx is bucketed as invalid credentials. An unmapped error degrades
    to the more general needs_reconnect rather than guessing at a more
    specific state it can't actually confirm.

    Raises InstagramAuthError (not a status value) for a transport failure
    — a network blip isn't evidence the connection itself is broken, so
    callers should keep the last-known status rather than treat this as a
    new one; see app/api/instagram.py's status route.
    """
    token = get_page_access_token(credential)
    url = (
        f"https://graph.facebook.com/{settings.instagram_graph_version}/"
        f"{credential.instagram_business_account_id}"
    )

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        try:
            resp = client.get(url, params={"access_token": token, "fields": "id"})
        except httpx.TransportError as exc:
            raise InstagramAuthError(
                f"Could not reach Meta's API to check connection health: {exc}"
            ) from exc

        if resp.status_code < 400:
            return CONNECTED

        try:
            error = resp.json().get("error", {})
        except ValueError:
            error = {}
        code = error.get("code")
        message = (error.get("message") or "").lower()

        if code == 190:
            return NEEDS_RECONNECT
        if code == 10 or "permission" in message:
            return PERMISSION_REVOKED
        return INVALID_CREDENTIALS
    finally:
        if owns_client:
            client.close()
