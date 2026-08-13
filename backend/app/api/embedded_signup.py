"""WhatsApp Embedded Signup API (/api/v1/whatsapp/embedded-signup) — Track B
prep (TODOS.md ONBOARD-E). Placeholder surface alongside, not replacing,
guided-manual v1 (app/api/whatsapp.py, still the production connect flow).

Every route 404s while `settings.enable_embedded_signup` is False — same
fail-closed reasoning app/core/config.py already applies to
`founder_clerk_user_ids`: an unconfigured/disabled feature is a missing
route, not a broken one a client could still hit. When the flag is on but
the provider still can't complete a real flow (no Meta Tech Provider
approval yet — see StubEmbeddedSignupProvider), routes return 503 rather
than 404: the feature is meant to exist on this deployment, it just isn't
ready yet.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.core.config import settings
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


class EmbeddedSignupCallbackRequest(BaseModel):
    code: str = Field(min_length=1, max_length=MAX_TOKEN_LENGTH)
    state: str = Field(min_length=1, max_length=MAX_TOKEN_LENGTH)


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
    return {
        "data": {
            "enabled": bool(settings.embedded_signup_config_id),
        }
    }


@router.post("/start")
def start_embedded_signup(
    principal: Principal = Depends(get_current_principal),
) -> dict:
    _require_enabled()
    provider = get_embedded_signup_provider()
    try:
        session = provider.start(business_id=principal.business_id)
    except EmbeddedSignupNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"data": {"config_id": session.config_id, "state": session.state}}


@router.post("/callback")
def embedded_signup_callback(
    payload: EmbeddedSignupCallbackRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Receives the authorization code Meta's popup hands back to the
    frontend (WHATSAPP_ONBOARDING_V2_DESIGN.md §5 — the frontend never talks
    to Meta's Graph API directly). A `success=False` result is a normal,
    expected outcome (wrong account, revoked, etc.) and returns 200 with the
    reason in `data.error`; only an unconfigured deployment 503s."""
    _require_enabled()
    provider = get_embedded_signup_provider()
    try:
        result = provider.complete(
            db,
            business_id=principal.business_id,
            authorization_code=payload.code,
            state=payload.state,
        )
    except EmbeddedSignupNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {
        "data": {
            "success": result.success,
            "display_phone_number": result.display_phone_number,
            "error": result.error,
        }
    }
