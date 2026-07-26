"""Timestamp serialization (Sprint 77).

Every datetime column in this schema is naive-but-UTC-implied (DEC-032) —
Python's bare `datetime.isoformat()` on a naive value produces a string with
no timezone marker (e.g. "2026-07-26T10:52:00"), and every major JS `Date`
parser (`new Date(...)`) interprets a timezone-less ISO string as *local*
browser time, not UTC. For any user outside UTC, every relative timestamp in
the product ("X ago", conversation/message times, Founder Dashboard and
Execution Trace timestamps, ...) was silently wrong by exactly the browser's
UTC offset — found live in production during RC-1's beta readiness audit.

`to_iso_utc()` is the one place that turns a stored datetime into the string
an API response sends — every manual `.isoformat()` call across the API
should go through this instead, so every timestamp this app ever emits is
unambiguous by construction, not by the discipline of each call site
remembering to append a suffix.
"""

from __future__ import annotations

from datetime import datetime, timezone


def to_iso_utc(value: datetime | None) -> str | None:
    """Naive (UTC-implied) or aware datetime -> unambiguous UTC ISO 8601
    string, or None through. Never performs a timezone *conversion* for the
    naive case — every datetime this schema stores is already UTC
    (DEC-032); this only makes that explicit in the string a client parses.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.isoformat() + "Z"
    return value.astimezone(timezone.utc).isoformat()
