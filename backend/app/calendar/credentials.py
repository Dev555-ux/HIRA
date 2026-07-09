"""Resolves a business's stored Google OAuth credentials into a ready-to-use
`google.oauth2.credentials.Credentials` object, and manages the
`CalendarCredential` row itself (store on connect/reconnect, remove on
disconnect).

Access-token refresh is handled transparently by googleapiclient's request
layer as long as `refresh_token`/`client_id`/`client_secret`/`token_uri` are
all present on the Credentials object — no manual refresh loop is needed here.
"""

from __future__ import annotations

import uuid

from google.oauth2.credentials import Credentials
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendar.oauth import SCOPES
from app.calendar.providers.base import CalendarNotConnectedError
from app.calendar.security import decrypt_token, encrypt_token
from app.core.config import settings
from app.models import CalendarCredential

TOKEN_URI = "https://oauth2.googleapis.com/token"
DEFAULT_CALENDAR_ID = "primary"


def store_credentials(
    db: Session,
    business_id: uuid.UUID,
    refresh_token: str,
    *,
    calendar_id: str = DEFAULT_CALENDAR_ID,
) -> CalendarCredential:
    """Create or replace this business's stored calendar credentials (connect/reconnect)."""
    existing = get_stored_credential(db, business_id)
    encrypted = encrypt_token(refresh_token)

    if existing is not None:
        existing.refresh_token_encrypted = encrypted
        existing.calendar_id = calendar_id
        existing.scopes = " ".join(SCOPES)
        db.commit()
        db.refresh(existing)
        return existing

    credential = CalendarCredential(
        business_id=business_id,
        refresh_token_encrypted=encrypted,
        calendar_id=calendar_id,
        scopes=" ".join(SCOPES),
    )
    db.add(credential)
    db.commit()
    db.refresh(credential)
    return credential


def get_stored_credential(db: Session, business_id: uuid.UUID) -> CalendarCredential | None:
    return db.scalars(
        select(CalendarCredential).where(CalendarCredential.business_id == business_id)
    ).first()


def disconnect(db: Session, business_id: uuid.UUID) -> bool:
    """Remove a business's stored calendar credentials. Returns False if none existed."""
    existing = get_stored_credential(db, business_id)
    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return True


def build_google_credentials(credential: CalendarCredential) -> Credentials:
    """Decrypt a stored CalendarCredential row into a live Credentials object."""
    return Credentials(
        token=None,
        refresh_token=decrypt_token(credential.refresh_token_encrypted),
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )


def get_google_credentials_for_business(db: Session, business_id: uuid.UUID) -> Credentials:
    """Raises CalendarNotConnectedError if this business hasn't connected a calendar yet."""
    credential = get_stored_credential(db, business_id)
    if credential is None:
        raise CalendarNotConnectedError("This business has not connected a Google Calendar")
    return build_google_credentials(credential)
