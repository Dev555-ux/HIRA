"""Stub `EmbeddedSignupProvider` (Track B prep, TODOS.md ONBOARD-E).

Both methods always raise `EmbeddedSignupNotConfiguredError` — there is no
Meta Tech Provider approval yet (TODOS.md ONBOARD-E: "the Meta Tech Provider
application has not been submitted"), so there is no real popup to launch and
no real authorization code to exchange. This is deliberately not a fake
"success" path: per WHATSAPP_ONBOARDING_V2_DESIGN.md, the real
`complete()` needs a live Graph API token exchange, a `/register` call, and a
`subscribed_apps` call, none of which can be invented without Meta's actual
API responses to test against.

Replace with a real provider (implementing the same `EmbeddedSignupProvider`
interface, registered in providers/__init__.py) once approval exists — no
change needed to the API routes that call `get_embedded_signup_provider()`.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.whatsapp.providers.base import (
    EmbeddedSignupNotConfiguredError,
    EmbeddedSignupProvider,
    EmbeddedSignupResult,
    EmbeddedSignupSession,
)


class StubEmbeddedSignupProvider(EmbeddedSignupProvider):
    def start(self, *, business_id: uuid.UUID) -> EmbeddedSignupSession:
        raise EmbeddedSignupNotConfiguredError(
            "Embedded Signup isn't available yet — Meta Tech Provider approval "
            "is still pending (see TODOS.md ONBOARD-E)."
        )

    def complete(
        self, db: Session, *, business_id: uuid.UUID, authorization_code: str, state: str
    ) -> EmbeddedSignupResult:
        raise EmbeddedSignupNotConfiguredError(
            "Embedded Signup isn't available yet — Meta Tech Provider approval "
            "is still pending (see TODOS.md ONBOARD-E)."
        )
