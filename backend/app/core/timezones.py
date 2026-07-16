"""Shared IANA timezone validation/resolution.

`Business.timezone` is a free-text column with two independent write paths
(onboarding's business creation, calendar settings) that must reject the same
invalid input, and several read paths (AI prompt building, working-hours
filtering) that must never crash the whole request over a bad stored value —
a single business's bad data shouldn't take down replies/availability for
everyone. One shared implementation for both.
"""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)


def validate_timezone(value: str) -> None:
    """Raise ValueError if `value` isn't a real IANA timezone key."""
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {value}") from exc


def safe_zoneinfo(value: str, *, business_id: object = None) -> ZoneInfo:
    """Resolve `value` to a ZoneInfo, falling back to UTC and logging a
    warning if it's not a real IANA key — validation at write time (see
    `validate_timezone`) should prevent this, but doesn't cover rows written
    before that validation existed."""
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError:
        logger.warning(
            "Unknown timezone %r for business %s; falling back to UTC", value, business_id
        )
        return ZoneInfo("UTC")
