"""Tests for app/calendar/security.py: Fernet encrypt/decrypt round-trip and
the "not configured" error path (DEC-032)."""

import pytest
from cryptography.fernet import Fernet

from app.calendar.providers.base import CalendarNotConfiguredError
from app.calendar.security import decrypt_token, encrypt_token
from app.core.config import settings


def test_encrypt_then_decrypt_roundtrips(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())

    encrypted = encrypt_token("a-real-refresh-token")

    assert encrypted != "a-real-refresh-token"
    assert decrypt_token(encrypted) == "a-real-refresh-token"


def test_encrypt_raises_when_key_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", "")

    with pytest.raises(CalendarNotConfiguredError):
        encrypt_token("token")


def test_decrypt_raises_when_key_rotated(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    encrypted = encrypt_token("token")

    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())

    with pytest.raises(CalendarNotConfiguredError):
        decrypt_token(encrypted)
