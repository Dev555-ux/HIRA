"""Outcome DTOs for the two operations a provider can fail at: connecting,
and sending.

Purpose: give every provider one shared, honest way to report success or
failure for these two operations, instead of each provider inventing its
own return shape (or raising exceptions for expected, business-as-usual
failures like "this credential is invalid").

Responsibilities: `ConnectionResult` reports whether a credential actually
works, for the connect/onboarding flow. `DeliveryReceipt` reports whether a
send actually landed, carrying the provider's own message id for later
delivery-status correlation.

Does NOT do: retry anything itself, decide what the caller should do next
beyond reporting `retryable`, or touch the database. A `DeliveryReceipt` is
not a `Message` row — turning one into the other is MessagingService's job.

Future integration point: `ChannelProvider.validate_credentials()` returns
`ConnectionResult`; `ChannelProvider.send()` returns `DeliveryReceipt`.
Both are also what `ChannelManager` hands back up to `MessagingService`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping


@dataclass(frozen=True)
class ConnectionResult:
    """`success=False` always carries `error` — callers never have to guess
    why a credential failed to validate."""

    success: bool
    external_account_id: str | None = None
    display_name: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class DeliveryReceipt:
    """`status="failed"` always carries `error`, same convention as
    ConnectionResult. `external_message_id` is None on failure — there is
    nothing to correlate a later delivery-status webhook against.

    `retryable` (Sprint 64A PR 6) is how a provider's single transport
    attempt tells ChannelManager whether trying again is worth it, without
    ChannelManager needing to know any provider-specific error shape (an
    HTTP status code, a platform error code, ...) — the whole point of
    normalizing a provider failure into a generic channel-level signal
    before it crosses back up. Meaningless when `status="sent"`; defaults
    to False (the safe choice — a provider that doesn't set this
    explicitly should never cause ChannelManager to retry blindly)."""

    status: Literal["sent", "failed"]
    external_message_id: str | None = None
    error: str | None = None
    retryable: bool = False
    raw: Mapping[str, object] = field(default_factory=dict)
