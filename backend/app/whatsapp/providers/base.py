"""Embedded Signup provider interface (Track B / ONBOARD-E prep).

Mirrors app/calendar/providers/base.py's shape: callers (the API layer)
depend only on `EmbeddedSignupProvider`, never on a concrete implementation.
Two implementations exist: `MetaEmbeddedSignupProvider`
(embedded_signup_meta.py), the real flow, and `StubEmbeddedSignupProvider`
(embedded_signup_stub.py), which an unconfigured deployment gets. The factory
in providers/__init__.py picks between them from configuration alone, so no
route has to know which one it's talking to.

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


# `EmbeddedSignupResult.error_code` values. Stable, machine-readable, and
# safe to show a client: the frontend maps each to its own copy, so no Meta
# error text, error number, or response body ever reaches a browser. Every
# failure the provider can produce has one — there is no "unknown" bucket a
# screen would have to guess at.
ERROR_STATE_INVALID = "state_invalid"
ERROR_PERMISSION_DENIED = "permission_denied"
ERROR_NO_WABA = "no_waba"
ERROR_NO_PHONE_NUMBER = "no_phone_number"
ERROR_PHONE_NUMBER_IN_USE = "phone_number_in_use"
ERROR_TOKEN_EXCHANGE_FAILED = "token_exchange_failed"
ERROR_REGISTRATION_FAILED = "registration_failed"
ERROR_PIN_MISMATCH = "pin_mismatch"
ERROR_SUBSCRIPTION_FAILED = "subscription_failed"
ERROR_META_UNAVAILABLE = "meta_unavailable"


@dataclass
class EmbeddedSignupResult:
    """Outcome of exchanging a callback's authorization code. `success=False`
    always carries `error` (engineer-readable) and `error_code` (one of the
    constants above, which is what the UI actually branches on) — callers
    never have to guess why, and never have to parse prose to find out."""

    success: bool
    phone_number_id: str | None = None
    whatsapp_business_account_id: str | None = None
    display_phone_number: str | None = None
    error: str | None = None
    error_code: str | None = None


class EmbeddedSignupError(RuntimeError):
    """Base error for the Embedded Signup provider."""


class EmbeddedSignupNotConfiguredError(EmbeddedSignupError):
    """This deployment can't attempt a real flow: the flag is off, the Tech
    Provider configuration is incomplete (app/meta.py), or no Meta-backed
    provider is registered yet."""


class EmbeddedSignupProvider(ABC):
    @abstractmethod
    def start(self, db: Session, *, business_id: uuid.UUID) -> EmbeddedSignupSession:
        """Prepare what the frontend needs to open Meta's popup, and record
        the attempt. Takes a session because the `state` it issues is only
        meaningful if it's also persisted — a signed state nothing stored
        can be replayed, which is exactly what `WhatsAppOnboardingAttempt`
        exists to prevent. Raises EmbeddedSignupNotConfiguredError if this
        deployment isn't ready to start a real flow."""

    @abstractmethod
    def complete(
        self,
        db: Session,
        *,
        business_id: uuid.UUID,
        authorization_code: str,
        state: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> EmbeddedSignupResult:
        """`waba_id`/`phone_number_id` are what Meta's popup reported to the
        browser via postMessage. They are hints, not facts: they arrive from
        a client and are therefore verified server-side against the token's
        own granular scopes and Meta's phone-number list before anything is
        stored. Omitting them is fully supported — the provider resolves
        both from the token itself.

        Receives the popup callback's authorization code, exchanges it
        for a Business Integration System User token, registers the phone
        number (`/register`), subscribes HIRA's webhook (`subscribed_apps`),
        and stores the resulting credentials — the same four backend steps
        WHATSAPP_ONBOARDING_V2_DESIGN.md §1.2/§5 lists as required. Returns
        an `EmbeddedSignupResult` reporting success or failure; never raises
        for an ordinary Meta-side failure (wrong account, revoked, etc.) —
        those are reported via `success=False`, not an exception. Raises
        EmbeddedSignupNotConfiguredError only if this deployment can't
        attempt the exchange at all."""
