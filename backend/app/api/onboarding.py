"""Onboarding API (/api/v1/onboarding) — Milestone A (business provisioning)
plus the AI Playground (ONBOARDING_ARCHITECTURE.md §4.4).

Routes:
- `GET /status` — does the calling Clerk identity already have a business?
  Used by the frontend right after login to decide dashboard vs. /onboarding.
- `POST /business` — create the Business + owner User for a first-time signup.
- `POST /playground/message` — synchronous AI test-drive (see app/ai/playground.py).

The provisioning routes sit behind `get_verified_clerk_user_id`, not
`get_current_principal`: a brand-new signup has a valid Clerk session but (by
definition) no `User` row yet, so the stricter dashboard dependency — which
401s on an unknown user — would wrongly reject exactly the request this flow
needs to allow. The playground route requires an existing business, so it uses
`get_current_principal` like every other dashboard route.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.playground import playground_reply
from app.auth.dependencies import Principal, get_current_principal, get_verified_clerk_user_id
from app.core.timezones import validate_timezone
from app.db.session import get_db
from app.models import Business
from app.services.provisioning import get_business_for_clerk_user, provision_business

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


class ProvisionBusinessRequest(BaseModel):
    name: str
    owner_email: str
    industry: str | None = None
    contact_email: str | None = None
    country: str | None = None
    timezone: str | None = None


class PlaygroundMessageRequest(BaseModel):
    message: str


def _looks_like_email(value: str) -> bool:
    return "@" in value and "." in value.split("@")[-1]


def _serialize_business(business: Business) -> dict:
    return {
        "id": str(business.id),
        "name": business.name,
        "industry": business.vertical,
        "contact_email": business.contact_email,
        "country": business.country,
        "timezone": business.timezone,
        "onboarding_status": business.onboarding_status,
        "whatsapp_connection_status": business.whatsapp_connection_status,
    }


@router.get("/status")
def onboarding_status(
    clerk_user_id: str = Depends(get_verified_clerk_user_id),
    db: Session = Depends(get_db),
) -> dict:
    logger.info("onboarding_status: looking up business for clerk_user_id=%s", clerk_user_id)
    try:
        business = get_business_for_clerk_user(db, clerk_user_id)
    except Exception:
        logger.exception(
            "onboarding_status: DB lookup failed for clerk_user_id=%s", clerk_user_id
        )
        raise
    if business is None:
        logger.info("onboarding_status: no business yet for clerk_user_id=%s", clerk_user_id)
        return {"data": {"has_business": False, "business": None}}
    logger.info(
        "onboarding_status: found business_id=%s for clerk_user_id=%s", business.id, clerk_user_id
    )
    return {"data": {"has_business": True, "business": _serialize_business(business)}}


@router.post("/business", status_code=status.HTTP_201_CREATED)
def create_business(
    payload: ProvisionBusinessRequest,
    clerk_user_id: str = Depends(get_verified_clerk_user_id),
    db: Session = Depends(get_db),
) -> dict:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Business name is required")
    if not payload.owner_email or not _looks_like_email(payload.owner_email):
        raise HTTPException(status_code=422, detail="A valid owner email is required")
    if payload.contact_email and not _looks_like_email(payload.contact_email):
        raise HTTPException(status_code=422, detail="Business email is not a valid email address")
    timezone = (payload.timezone or "").strip() or None
    if timezone is not None:
        try:
            validate_timezone(timezone)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    business = provision_business(
        db,
        clerk_user_id=clerk_user_id,
        owner_email=payload.owner_email,
        name=name,
        industry=(payload.industry or "").strip() or None,
        contact_email=(payload.contact_email or "").strip() or None,
        country=(payload.country or "").strip() or None,
        timezone=timezone,
    )
    return {"data": _serialize_business(business)}


@router.post("/playground/message")
def playground_message(
    payload: PlaygroundMessageRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is required")

    response, retrieved, body = playground_reply(db, principal.business_id, message)
    return {
        "data": {
            "reply": body,
            "model": response.model,
            "retrieved": [
                {"id": str(entry.id), "title": entry.title, "content": entry.content}
                for entry in retrieved
            ],
        }
    }
