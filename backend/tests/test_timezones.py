"""Tests for app/core/timezones.py: the shared IANA timezone validate/resolve
helpers used by both onboarding's business creation and calendar settings
(write paths), and by app/ai/prompts.py + app/calendar/working_hours.py
(read paths that must never crash on bad stored data)."""

from zoneinfo import ZoneInfo

import pytest

from app.core.timezones import safe_zoneinfo, validate_timezone


def test_validate_timezone_accepts_real_iana_key():
    validate_timezone("Asia/Kolkata")  # no raise


def test_validate_timezone_rejects_unknown_key():
    with pytest.raises(ValueError, match="Unknown timezone"):
        validate_timezone("asia")


def test_safe_zoneinfo_resolves_real_key():
    assert safe_zoneinfo("Asia/Kolkata") == ZoneInfo("Asia/Kolkata")


def test_safe_zoneinfo_falls_back_to_utc_for_unknown_key():
    assert safe_zoneinfo("asia") == ZoneInfo("UTC")
