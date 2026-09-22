"""WhatsApp Embedded Signup API (/api/v1/whatsapp/embedded-signup) — Track B
(TODOS.md ONBOARD-E). Sits alongside, and does not replace, guided-manual v1
(app/api/whatsapp.py, still the production connect flow).

Every route 404s while `settings.enable_embedded_signup` is False — same
fail-closed reasoning app/core/config.py already applies to
`founder_clerk_user_ids`: an unconfigured/disabled feature is a missing
route, not a broken one a client could still hit. When the flag is on but
the provider still can't complete a real flow, routes return 503 rather
than 404: the feature is meant to exist on this deployment, it just isn't
ready yet.

Sprint 83: the real `MetaEmbeddedSignupProvider` is live. "Not ready" now
means only one thing — this deployment hasn't been given Stoneveil's Meta
app credentials (`META_APP_ID`/`META_APP_SECRET`/`META_APP_CONFIG_ID`), so
the factory hands back the stub and these routes 503. A configured
deployment runs the real flow.

Two routes, and the split matters: `/start` opens a single-use onboarding
attempt and returns the `config_id` + `state` the JS SDK needs; `/callback`
takes back the authorization code Meta's popup gave the browser. The
frontend never calls Meta's Graph API and never holds an access token — it
holds a short-lived code that is worthless without the app secret.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import meta
from app.auth.dependencies import Principal, get_current_principal
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.whatsapp.providers import (
    EmbeddedSignupNotConfiguredError,
    get_embedded_signup_provider,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp/embedded-signup", tags=["whatsapp", "embedded-signup"])

# Meta's authorization code / CSRF state are short opaque strings, not
# human-typed text — bounded the same way ConnectWhatsAppRequest bounds
# access_token/app_secret in app/api/whatsapp.py.
MAX_TOKEN_LENGTH = 4096


# Meta object ids are short numeric strings; bounded like every other
# request field in this app rather than left open-ended.
MAX_ID_LENGTH = 64


class EmbeddedSignupCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_TOKEN_LENGTH)
    state: str = Field(min_length=1, max_length=MAX_TOKEN_LENGTH)
    # What Meta's popup reported to the browser via postMessage. Optional,
    # and treated as a hint the provider verifies against the token's own
    # granular scopes and Meta's phone-number list — never as fact (see
    # app/whatsapp/providers/embedded_signup_meta.py).
    waba_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)
    phone_number_id: str | None = Field(default=None, max_length=MAX_ID_LENGTH)


def _require_enabled() -> None:
    if not settings.enable_embedded_signup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)


@router.get("/config")
def get_embedded_signup_config(
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Whether this deployment can offer Embedded Signup at all — the
    frontend's entry screen (Track B) uses this to decide whether to render
    "Continue with Facebook" or fall back to the manual connect flow."""
    _require_enabled()
    return {"data": {"enabled": meta.tech_provider_configured()}}


@router.post("/start")
@limiter.limit(lambda: settings.rate_limit_embedded_signup)
def start_embedded_signup(
    request: Request,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Opens an onboarding attempt and returns what the JS SDK needs. The
    `state` returned here is single-use and expiring; the frontend hands it
    straight back on /callback and never stores or reuses it."""
    _require_enabled()
    provider = get_embedded_signup_provider()
    try:
        session = provider.start(db, business_id=principal.business_id)
    except EmbeddedSignupNotConfiguredError as exc:
        logger.warning(
            "whatsapp.onboarding.failed business_id=%s method=embedded_signup "
            "reason=provider_not_configured",
            principal.business_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {"data": {"config_id": session.config_id, "state": session.state}}


@router.post("/callback")
@limiter.limit(lambda: settings.rate_limit_embedded_signup)
def embedded_signup_callback(
    request: Request,
    payload: EmbeddedSignupCallbackRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Receives the authorization code Meta's popup hands back to the
    frontend (WHATSAPP_ONBOARDING_V2_DESIGN.md §5 — the frontend never talks
    to Meta's Graph API directly).

    A `success=False` result is a normal, expected outcome (a cancelled
    consent, a number already connected elsewhere, an expired state) and
    returns 200 with a machine-readable `error_code` the UI maps to its own
    copy. Only a deployment that can't attempt the flow at all 503s."""
    _require_enabled()
    provider = get_embedded_signup_provider()
    try:
        result = provider.complete(
            db,
            business_id=principal.business_id,
            authorization_code=payload.code,
            state=payload.state,
            waba_id=payload.waba_id,
            phone_number_id=payload.phone_number_id,
        )
    except EmbeddedSignupNotConfiguredError as exc:
        logger.warning(
            "whatsapp.onboarding.failed business_id=%s method=embedded_signup "
            "reason=provider_not_configured",
            principal.business_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc
    return {
        "data": {
            "success": result.success,
            "display_phone_number": result.display_phone_number,
            # `error_code` is what the UI branches on; `error` is the
            # engineer-readable reason, already logged by the provider.
            # Neither carries a Meta response body, a token, or a scope name.
            "error_code": result.error_code,
        }
    }
