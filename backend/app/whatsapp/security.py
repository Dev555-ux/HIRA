"""Encrypts WhatsApp credentials at rest with Fernet (Sprint 69).

Reuses `CALENDAR_ENCRYPTION_KEY` rather than introducing a new required env
var — same reasoning as DEC-032's own choice to reuse one key for both
encryption and OAuth-state HMAC-signing: one key, another use, not a new
secret for an MVP that doesn't need it split out. Rotating that key
invalidates every business's stored WhatsApp credentials the same way it
already invalidates stored Calendar refresh tokens.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.whatsapp.errors import WhatsAppNotConfiguredError


def _fernet() -> Fernet:
    if not settings.calendar_encryption_key:
        raise WhatsAppNotConfiguredError("CALENDAR_ENCRYPTION_KEY is not set")
    return Fernet(settings.calendar_encryption_key.encode())


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise WhatsAppNotConfiguredError(
            "Stored WhatsApp credential could not be decrypted — CALENDAR_ENCRYPTION_KEY may have changed"
        ) from exc
