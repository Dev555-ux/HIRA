"""Manages a business's own stored WhatsApp credentials (Sprint 69) — store
on connect/reconnect, remove on disconnect, resolve for sending/verifying —
mirroring app/calendar/credentials.py's shape for CalendarCredential.
"""

from __future__ import annotations

import uuid
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import meta
from app.meta import TOKEN_SOURCE_EMBEDDED_SIGNUP, TOKEN_SOURCE_MANUAL
from app.models import WhatsAppCredential
from app.whatsapp.errors import WhatsAppCredentialInvalidError
from app.whatsapp.security import decrypt_secret, encrypt_secret


def store_credentials(
    db: Session,
    business_id: uuid.UUID,
    *,
    access_token: str,
    app_secret: str,
) -> WhatsAppCredential:
    """Create or replace this business's stored WhatsApp credentials
    (connect/reconnect — both go through the same idempotent path).

    This is the manual-onboarding writer: it always produces a
    `token_source="manual"` row, which is why `token_source` is set
    explicitly on the update branch too. A business that connected through
    Embedded Signup and later reconnects by pasting their own credentials
    here really has become a manual connection, and their webhook signatures
    really will start arriving under their own app secret from that moment —
    leaving a stale `embedded_signup` marker behind would send every one of
    their inbound messages to be verified against the wrong secret.
    """
    existing = get_stored_credential(db, business_id)
    encrypted_token = encrypt_secret(access_token)
    encrypted_secret = encrypt_secret(app_secret)

    if existing is not None:
        existing.access_token_encrypted = encrypted_token
        existing.app_secret_encrypted = encrypted_secret
        existing.token_source = TOKEN_SOURCE_MANUAL
        db.commit()
        db.refresh(existing)
        return existing

    credential = WhatsAppCredential(
        business_id=business_id,
        access_token_encrypted=encrypted_token,
        app_secret_encrypted=encrypted_secret,
        token_source=TOKEN_SOURCE_MANUAL,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def store_embedded_signup_credentials(
    db: Session,
    business_id: uuid.UUID,
    *,
    access_token: str,
    token_type: str | None,
    granted_scopes: str | None,
    token_expires_at: datetime | None,
    two_factor_pin: str,
) -> WhatsAppCredential:
    """The Embedded Signup counterpart to `store_credentials` above: same
    create-or-replace shape, `token_source="embedded_signup"`, and
    `app_secret_encrypted` cleared to NULL because these businesses have no
    app secret of their own — Meta signs their webhooks with Stoneveil's
    (see app/meta.py and `get_webhook_signing_secret` below).

    Clearing the app secret on the update branch matters: a business that
    first connected manually and then reconnects through Embedded Signup
    must stop being verified against their old secret at the same moment
    Meta stops signing with it. Leaving a stale value behind would reject
    every inbound message from that point on.
    """
    existing = get_stored_credential(db, business_id)
    values = {
        "access_token_encrypted": encrypt_secret(access_token),
        "app_secret_encrypted": None,
        "token_source": TOKEN_SOURCE_EMBEDDED_SIGNUP,
        "token_type": token_type,
        "granted_scopes": granted_scopes,
        "token_expires_at": token_expires_at,
        "two_factor_pin_encrypted": encrypt_secret(two_factor_pin),
    }

    if existing is not None:
        for field, value in values.items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    credential = WhatsAppCredential(business_id=business_id, **values)
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def get_two_factor_pin(credential: WhatsAppCredential) -> str | None:
    """The PIN HIRA generated for this number's two-step verification, or
    None for a manual connection (where the owner set their own inside
    Meta's console and HIRA never learns it).

    Reconnecting reuses this rather than generating a new one: Meta rejects
    a `/register` call whose PIN doesn't match the one already set on the
    number (error 133005), so a fresh PIN on every reconnect would make the
    second connection attempt fail for a number HIRA itself registered.
    """
    if credential.two_factor_pin_encrypted is None:
        return None
    return decrypt_secret(credential.two_factor_pin_encrypted)


def get_stored_credential(db: Session, business_id: uuid.UUID) -> WhatsAppCredential | None:
    return db.scalars(
        select(WhatsAppCredential).where(WhatsAppCredential.business_id == business_id)
    ).first()


def disconnect(db: Session, business_id: uuid.UUID) -> bool:
    """Remove a business's stored WhatsApp credentials. Returns False if none existed."""
    existing = get_stored_credential(db, business_id)
    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return True


def get_access_token(credential: WhatsAppCredential) -> str:
    return decrypt_secret(credential.access_token_encrypted)


def get_webhook_signing_secret(credential: WhatsAppCredential) -> str | None:
    """The app secret Meta signed *this* business's webhook delivery with —
    the single place that question is answered (Sprint 82).

    It has two answers, because there are now two onboarding architectures
    (app/meta.py):

    * `manual` — the business owns the Meta App that sends its webhooks, so
      the signature is theirs and the secret is the one they pasted at
      connect time, stored encrypted on this row.
    * `embedded_signup` — Stoneveil's Tech Provider app serves them, so Meta
      signs with `META_APP_SECRET`. There is no per-business secret to store
      and none is stored.

    Returns None when no secret can be resolved — an Embedded Signup
    business on a deployment where `META_APP_SECRET` isn't configured. The
    caller must reject the delivery in that case: unverifiable is not
    trusted. Raises WhatsAppNotConfiguredError if a stored secret exists but
    can't be decrypted (a rotated encryption key), same as before.
    """
    if credential.token_source == TOKEN_SOURCE_EMBEDDED_SIGNUP:
        return meta.app_secret() or None
    if credential.app_secret_encrypted is None:
        return None
    return decrypt_secret(credential.app_secret_encrypted)


def _meta_error_code(resp: httpx.Response) -> int | None:
    """Meta's numeric error code, or None if the body isn't the JSON shape
    Graph normally returns. Never the message, never the body."""
    try:
        return resp.json().get("error", {}).get("code")
    except ValueError:
        return None


def verify_whatsapp_credentials(
    phone_number_id: str,
    access_token: str,
    *,
    client: httpx.Client | None = None,
) -> str | None:
    """One live Graph API call proving `access_token` actually has access to
    `phone_number_id`, made *before* storing anything — so a typo'd token or
    the wrong phone number id fails immediately with a specific reason,
    rather than silently "connecting" and only failing on the first real
    send. Raises WhatsAppCredentialInvalidError on any failure.

    Returns the real, dialable `display_phone_number` Meta reports for this
    ID (Sprint 72) — `phone_number_id` itself is a Meta-internal identifier,
    not something a business owner would recognize as "their number." `None`
    if Meta's response omits the field (shouldn't normally happen since it's
    explicitly requested below, but this call already has a real customer's
    setup depending on it, so a missing field degrades to "don't show a
    number" rather than raising).
    """
    url = meta.graph_url(phone_number_id)
    headers = {"Authorization": f"Bearer {access_token}"}

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        try:
            resp = client.get(url, headers=headers, params={"fields": "display_phone_number"})
        except httpx.TransportError as exc:
            raise WhatsAppCredentialInvalidError(
                f"Could not reach Meta's API to verify these credentials: {exc}"
            ) from exc

        if resp.status_code == 401:
            raise WhatsAppCredentialInvalidError(
                "Meta rejected the access token — check you copied the full System User token."
            )
        if resp.status_code == 404:
            raise WhatsAppCredentialInvalidError(
                "Meta couldn't find a phone number with that ID — double-check the Phone Number ID."
            )
        if resp.status_code >= 400:
            # Sprint 84 security review: this used to interpolate `resp.text`,
            # putting Meta's raw error body into a 422 the browser renders.
            # Graph error payloads quote request parameters back, so that was
            # an unbounded disclosure channel on the one endpoint a business
            # owner submits credentials to. Status and Meta's own error code
            # are enough to debug with and carry nothing back. Matches what
            # app/whatsapp/graph.py::_error_summary already does for the
            # Embedded Signup path.
            raise WhatsAppCredentialInvalidError(
                f"Meta rejected these credentials: {resp.status_code} code={_meta_error_code(resp)}"
            )
        return resp.json().get("display_phone_number")
    finally:
        if owns_client:
            client.close()
