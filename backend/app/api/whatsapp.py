"""WhatsApp API (/api/v1/whatsapp) — Sprint 69 self-serve connection
("guided-manual v1", per TODOS.md ONBOARD-D).

A business brings its own Meta System User token + app secret — created on
Meta's own site, following in-app instructions — rather than the founder
manually running a script (app/onboarding/whatsapp.py, now an ops-only
utility for repointing an existing business's number, not part of this
flow). True one-click "Embedded Signup" (TODOS.md ONBOARD-E) needs Meta's
Tech Provider approval, an external, non-engineering process not yet
granted — this is the realistic self-serve option available today.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.models import Business
from app.whatsapp import credentials as whatsapp_credentials
from app.whatsapp.errors import WhatsAppCredentialInvalidError, WhatsAppNotConfiguredError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/whatsapp", tags=["whatsapp"])

MAX_ID_LENGTH = 64
# Meta System User tokens/app secrets are long opaque strings, not
# human-typed text — generous but bounded, matching the project's existing
# convention of capping every request field rather than leaving any unbounded.
MAX_SECRET_LENGTH = 4096


class ConnectWhatsAppRequest(BaseModel):
    phone_number_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    whatsapp_business_account_id: str = Field(min_length=1, max_length=MAX_ID_LENGTH)
    access_token: str = Field(min_length=1, max_length=MAX_SECRET_LENGTH)
    app_secret: str = Field(min_length=1, max_length=MAX_SECRET_LENGTH)


def _mask(phone_number_id: str | None) -> str | None:
    if not phone_number_id:
        return None
    if len(phone_number_id) <= 4:
        return "••••"
    return f"••••{phone_number_id[-4:]}"


def _serialize_status(business: Business, stored) -> dict:
    return {
        "connected": stored is not None,
        "status": business.whatsapp_connection_status,
        "phone_number_id_masked": _mask(business.whatsapp_phone_number_id),
        "connected_at": stored.created_at.isoformat() if stored else None,
    }


@router.get("/status")
def get_whatsapp_status(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    business = db.get(Business, principal.business_id)
    stored = whatsapp_credentials.get_stored_credential(db, principal.business_id)
    return {"data": _serialize_status(business, stored)}


@router.post("/connect")
def connect_whatsapp(
    payload: ConnectWhatsAppRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """Verifies the submitted credentials against Meta's own API *before*
    storing anything (a typo'd token fails immediately with a specific
    reason, not on the first real customer send), then stores them
    encrypted and marks the business connected. Also serves as "reconnect"
    — store_credentials is create-or-replace, so submitting new credentials
    for an already-connected business just replaces them.
    """
    try:
        whatsapp_credentials.verify_whatsapp_credentials(
            payload.phone_number_id, payload.access_token
        )
    except WhatsAppCredentialInvalidError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    try:
        whatsapp_credentials.store_credentials(
            db,
            principal.business_id,
            access_token=payload.access_token,
            app_secret=payload.app_secret,
        )
    except WhatsAppNotConfiguredError as exc:
        # The encryption key itself isn't set on this deployment — a
        # deployment/config gap, not something the business owner can fix.
        logger.error("WhatsApp connect attempted but not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp connection isn't available on this deployment yet.",
        ) from exc

    business = db.get(Business, principal.business_id)
    business.whatsapp_phone_number_id = payload.phone_number_id
    business.whatsapp_business_account_id = payload.whatsapp_business_account_id
    business.whatsapp_connection_status = "connected"
    db.commit()

    stored = whatsapp_credentials.get_stored_credential(db, principal.business_id)
    return {"data": _serialize_status(business, stored)}


@router.post("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_whatsapp(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    """Clears both the stored credential and the Business-level fields that
    mirror connection state — a clean "as if never connected" state, so a
    business mid-disconnect can't linger with a stale phone number that
    silently 403s at the webhook (indistinguishable from an unrelated
    unknown number) instead of honestly showing "not connected" everywhere
    that reads whatsapp_connection_status.
    """
    whatsapp_credentials.disconnect(db, principal.business_id)
    business = db.get(Business, principal.business_id)
    business.whatsapp_phone_number_id = None
    business.whatsapp_business_account_id = None
    business.whatsapp_connection_status = "not_connected"
    db.commit()
