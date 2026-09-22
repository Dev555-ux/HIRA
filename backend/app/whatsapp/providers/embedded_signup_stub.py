"""Stub `EmbeddedSignupProvider` — what an *unconfigured* deployment gets.

Not a leftover: `MetaEmbeddedSignupProvider` (embedded_signup_meta.py) is the
real implementation and is what a configured deployment gets. This one is
returned by the factory when `META_APP_ID`/`META_APP_SECRET`/
`META_APP_CONFIG_ID` aren't all set — local dev, a staging box, or production
before those variables are filled in.

Both methods raise `EmbeddedSignupNotConfiguredError`, which the API turns
into a 503 and the frontend into "use manual setup instead." Refusing up
front is the point: without an app secret the flow cannot get past the token
exchange, so failing at the first step with a clear reason beats opening
Meta's popup, walking an owner through six screens, and failing at the end.
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


_NOT_CONFIGURED = (
    "Embedded Signup isn't configured on this deployment — META_APP_ID, "
    "META_APP_SECRET and META_APP_CONFIG_ID must all be set."
)


class StubEmbeddedSignupProvider(EmbeddedSignupProvider):
    def start(self, db: Session, *, business_id: uuid.UUID) -> EmbeddedSignupSession:
        raise EmbeddedSignupNotConfiguredError(_NOT_CONFIGURED)

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
        raise EmbeddedSignupNotConfiguredError(_NOT_CONFIGURED)
