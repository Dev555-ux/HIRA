"""Tests for app/core/time.py::to_iso_utc (Sprint 77)."""

from datetime import datetime, timezone

from app.core.time import to_iso_utc


def test_none_passes_through():
    assert to_iso_utc(None) is None


def test_naive_datetime_gets_an_explicit_utc_suffix():
    value = datetime(2026, 7, 26, 10, 52, 0)

    result = to_iso_utc(value)

    assert result == "2026-07-26T10:52:00Z"
    # The exact bug this closes: a bare .isoformat() has no marker at all,
    # and every major JS Date parser then reads it as local time, not UTC.
    assert result != value.isoformat()
    assert result.endswith("Z")


def test_naive_datetime_with_microseconds():
    value = datetime(2026, 7, 26, 10, 52, 0, 123456)

    assert to_iso_utc(value) == "2026-07-26T10:52:00.123456Z"


def test_aware_utc_datetime_is_preserved_not_double_converted():
    value = datetime(2026, 7, 26, 10, 52, 0, tzinfo=timezone.utc)

    assert to_iso_utc(value) == "2026-07-26T10:52:00+00:00"


def test_aware_non_utc_datetime_is_normalized_to_utc():
    from datetime import timedelta

    ist = timezone(timedelta(hours=5, minutes=30))
    value = datetime(2026, 7, 26, 16, 22, 0, tzinfo=ist)  # 10:52 UTC

    result = to_iso_utc(value)

    assert result == "2026-07-26T10:52:00+00:00"
