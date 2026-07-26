"""Manages a business's own stored WhatsApp credentials (Sprint 69) — store
on connect/reconnect, remove on disconnect, resolve for sending/verifying —
mirroring app/calendar/credentials.py's shape for CalendarCredential.
"""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
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
    (connect/reconnect — both go through the same idempotent path)."""
    existing = get_stored_credential(db, business_id)
    encrypted_token = encrypt_secret(access_token)
    encrypted_secret = encrypt_secret(app_secret)

    if existing is not None:
        existing.access_token_encrypted = encrypted_token
        existing.app_secret_encrypted = encrypted_secret
        db.commit()
        db.refresh(existing)
        return existing

    credential = WhatsAppCredential(
        business_id=business_id,
        access_token_encrypted=encrypted_token,
        app_secret_encrypted=encrypted_secret,
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


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


def get_app_secret(credential: WhatsAppCredential) -> str:
    return decrypt_secret(credential.app_secret_encrypted)


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
    url = f"{settings.whatsapp_api_base}/{settings.whatsapp_graph_version}/{phone_number_id}"
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
            raise WhatsAppCredentialInvalidError(
                f"Meta rejected these credentials: {resp.status_code} {resp.text}"
            )
        return resp.json().get("display_phone_number")
    finally:
        if owns_client:
            client.close()
