"""Embedded Signup provider interface (Track B / ONBOARD-E prep).

Mirrors app/calendar/providers/base.py's shape: callers (the API layer)
depend only on `EmbeddedSignupProvider`, never on a concrete implementation.
Today the only implementation is `StubEmbeddedSignupProvider`
(embedded_signup_stub.py) — Meta Tech Provider approval isn't granted yet
(TODOS.md ONBOARD-E), so there is nothing real to implement against. A real
`MetaEmbeddedSignupProvider` is added later by implementing this interface
and registering it in providers/__init__.py — no change to the API routes
that call it.

Does not replace or touch app/whatsapp/credentials.py or app/api/whatsapp.py
(the guided-manual v1 connect flow) — that remains the production path.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from sqlalchemy.orm import Session


@dataclass
class EmbeddedSignupSession:
    """What the frontend needs to launch Meta's hosted popup (Embedded
    Signup v4, per WHATSAPP_ONBOARDING_V2_DESIGN.md §5's `FB.login` call)."""

    config_id: str
    state: str  # CSRF-protection token, verified again in complete()


@dataclass
class EmbeddedSignupResult:
    """Outcome of exchanging a callback's authorization code. `success=False`
    always carries `error` — callers never have to guess why."""

    success: bool
    phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    display_phone_number: str | None = None
    error: str | None = None


class EmbeddedSignupError(RuntimeError):
    """Base error for the Embedded Signup provider."""


class EmbeddedSignupNotConfiguredError(EmbeddedSignupError):
    """The flag is off, `config_id` is unset, or (today) Meta Tech Provider
    approval doesn't exist yet — there is no real flow to start or complete."""


class EmbeddedSignupProvider(ABC):
    @abstractmethod
    def start(self, *, business_id: uuid.UUID) -> EmbeddedSignupSession:
        """Prepare what the frontend needs to open Meta's popup. Raises
        EmbeddedSignupNotConfiguredError if this deployment isn't ready to
        start a real flow."""

    @abstractmethod
    def complete(
        self, db: Session, *, business_id: uuid.UUID, authorization_code: str, state: str
    ) -> EmbeddedSignupResult:
        """Receives the popup callback's authorization code, exchanges it
        for a Business Integration System User token, registers the phone
        number (`/register`), subscribes HIRA's webhook (`subscribed_apps`),
        and stores the resulting credentials — the same four backend steps
        WHATSAPP_ONBOARDING_V2_DESIGN.md §1.2/§5 lists as required. Returns
        an `EmbeddedSignupResult` reporting success or failure; never raises
        for an ordinary Meta-side failure (wrong account, revoked, etc.) —
        those are reported via `success=False`, not an exception. Raises
        EmbeddedSignupNotConfiguredError only if this deployment can't
        attempt the exchange at all."""
