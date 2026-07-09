"""Encrypts calendar refresh tokens at rest with Fernet (DEC-032).

`CALENDAR_ENCRYPTION_KEY` is a single symmetric key shared by every business —
rotating it invalidates every already-stored refresh token (see .env.example).
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.calendar.providers.base import CalendarNotConfiguredError
from app.core.config import settings


def _fernet() -> Fernet:
    if not settings.calendar_encryption_key:
        raise CalendarNotConfiguredError("CALENDAR_ENCRYPTION_KEY is not set")
    return Fernet(settings.calendar_encryption_key.encode())


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise CalendarNotConfiguredError(
            "Stored refresh token could not be decrypted — CALENDAR_ENCRYPTION_KEY may have changed"
        ) from exc
