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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.core.config import settings
from app.db.session import get_db
from app.models import Business, Message
from app.whatsapp import credentials as whatsapp_credentials
from app.whatsapp.errors import WhatsAppCredentialInvalidError, WhatsAppNotConfiguredError

PHONE_NUMBER_IN_USE_DETAIL = (
    "This WhatsApp phone number is already connected to a different business."
)

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


def _latest_inbound_at(db: Session, business_id, *, since) -> str | None:
    """The real production signal Task B needs: the most recent *inbound*
    Message actually persisted for this business, which only exists once
    `app/webhooks/whatsapp.py::_persist_inbound` has processed a real,
    signature-verified webhook delivery. Deliberately not inferred from
    stored credentials or `whatsapp_connection_status` — those only prove
    the token was valid, not that a message has ever arrived.

    `since` (the current credential's `connected_at`) scopes this to *this*
    connection: without it, a business that disconnects and reconnects (e.g.
    swapping to a different number) would see the wizard's verify step
    immediately report success using a message from the *previous*
    connection — found live against real local dev data during Sprint 71
    release verification, not caught by unit tests seeded with fresh rows."""
    query = select(Message.created_at).where(
        Message.business_id == business_id, Message.direction == "inbound"
    )
    if since is not None:
        query = query.where(Message.created_at >= since)
    latest = db.scalars(query.order_by(Message.created_at.desc()).limit(1)).first()
    return latest.isoformat() if latest else None


def _serialize_status(business: Business, stored, db: Session) -> dict:
    return {
        "connected": stored is not None,
        "status": business.whatsapp_connection_status,
        "phone_number_id_masked": _mask(business.whatsapp_phone_number_id),
        "connected_at": stored.created_at.isoformat() if stored else None,
        "last_inbound_at": _latest_inbound_at(
            db, business.id, since=stored.created_at if stored else None
        ),
    }


def _callback_url(request: Request) -> str:
    if settings.railway_public_domain:
        return f"https://{settings.railway_public_domain}/webhooks/whatsapp"
    return str(request.base_url).rstrip("/") + "/webhooks/whatsapp"


@router.get("/status")
def get_whatsapp_status(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    business = db.get(Business, principal.business_id)
    stored = whatsapp_credentials.get_stored_credential(db, principal.business_id)
    return {"data": _serialize_status(business, stored, db)}


@router.get("/webhook-config")
def get_webhook_config(
    request: Request,
    principal: Principal = Depends(get_current_principal),
) -> dict:
    """Static values every business must paste into their own Meta App's
    webhook configuration (Callback URL + Verify Token) — surfaced here
    (Sprint 71, Task A) so the connect wizard can show them directly instead
    of only pointing at developer docs. Identical for every business: the
    verify token is intentionally shared, not a secret (DEC-038)."""
    return {
        "data": {
            "callback_url": _callback_url(request),
            "verify_token": settings.whatsapp_verify_token,
        }
    }


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

    A phone_number_id can belong to only one business: the webhook
    (app/webhooks/whatsapp.py) routes an inbound message to whichever
    business row has that phone_number_id, so two businesses sharing one
    would mean the second connect silently steals the first's traffic.
    Checked up front (cheap, catches the common sequential case before the
    live Meta verification call), and enforced again by `db.flush()` below
    against `uq_businesses_whatsapp_phone_number_id` (the actual race-proof
    guard) *before* any credential is stored — so a request that loses that
    race never leaves an orphaned WhatsAppCredential behind.
    """
    try:
        whatsapp_credentials.verify_whatsapp_credentials(
            payload.phone_number_id, payload.access_token
        )
    except WhatsAppCredentialInvalidError as exc:
        raise HTTPException(status_code=422, detail=exc.reason) from exc

    conflicting = db.scalars(
        select(Business.id).where(
            Business.whatsapp_phone_number_id == payload.phone_number_id,
            Business.id != principal.business_id,
        )
    ).first()
    if conflicting is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=PHONE_NUMBER_IN_USE_DETAIL)

    business = db.get(Business, principal.business_id)
    business.whatsapp_phone_number_id = payload.phone_number_id
    business.whatsapp_business_account_id = payload.whatsapp_business_account_id
    business.whatsapp_connection_status = "connected"
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=PHONE_NUMBER_IN_USE_DETAIL
        ) from None

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
        db.rollback()
        logger.error("WhatsApp connect attempted but not configured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="WhatsApp connection isn't available on this deployment yet.",
        ) from exc

    stored = whatsapp_credentials.get_stored_credential(db, principal.business_id)
    return {"data": _serialize_status(business, stored, db)}


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
