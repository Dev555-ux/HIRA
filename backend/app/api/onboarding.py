"""Onboarding API (/api/v1/onboarding) — Milestone A (business provisioning)
plus Demo Chat (ONBOARDING_ARCHITECTURE.md §4.4; formerly "Playground").

Routes:
- `GET /status` — does the calling Clerk identity already have a business?
  Used by the frontend right after login to decide dashboard vs. /onboarding.
- `POST /business` — create the Business + owner User for a first-time signup.
- `POST /playground/message` — one Demo Chat turn (see app/ai/playground.py).
- `GET /playground/history` — the same conversation's persisted messages, so
  the frontend can restore the transcript after a page refresh instead of
  losing it to local-only state.

The provisioning routes sit behind `get_verified_clerk_user_id`, not
`get_current_principal`: a brand-new signup has a valid Clerk session but (by
definition) no `User` row yet, so the stricter dashboard dependency — which
401s on an unknown user — would wrongly reject exactly the request this flow
needs to allow. The Demo Chat routes require an existing business, so they use
`get_current_principal` like every other dashboard route.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.playground import get_or_create_playground_conversation, playground_reply
from app.auth.dependencies import Principal, get_current_principal, get_verified_clerk_user_id
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.timezones import validate_timezone
from app.db.session import get_db
from app.models import Business, Message
from app.services.provisioning import get_business_for_clerk_user, provision_business

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

# Sprint 52B: matches each field's own Business/User column length (see
# app/models.py) — without these, an oversized value fails at commit with a
# raw DB error instead of a clean 422.
MAX_NAME_LENGTH = 255
MAX_EMAIL_LENGTH = 320
MAX_INDUSTRY_LENGTH = 100
MAX_COUNTRY_LENGTH = 100
MAX_TIMEZONE_LENGTH = 64
# Demo Chat has no document upload — this is a chat message, not a document
# (that's what Business Knowledge/website-import are for) — bounds the cost
# of a single Groq/Claude call, matching UpdateDraftRequest's existing
# MAX_DRAFT_LENGTH convention (app/api/dashboard.py) for a "message body".
MAX_PLAYGROUND_MESSAGE_LENGTH = 4096


class ProvisionBusinessRequest(BaseModel):
    name: str = Field(max_length=MAX_NAME_LENGTH)
    owner_email: str = Field(max_length=MAX_EMAIL_LENGTH)
    industry: str | None = Field(default=None, max_length=MAX_INDUSTRY_LENGTH)
    contact_email: str | None = Field(default=None, max_length=MAX_EMAIL_LENGTH)
    country: str | None = Field(default=None, max_length=MAX_COUNTRY_LENGTH)
    timezone: str | None = Field(default=None, max_length=MAX_TIMEZONE_LENGTH)


class PlaygroundMessageRequest(BaseModel):
    message: str = Field(max_length=MAX_PLAYGROUND_MESSAGE_LENGTH)


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
@limiter.limit(lambda: settings.rate_limit_business_creation)
def create_business(
    request: Request,
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


def _serialize_playground_message(message: Message) -> dict:
    # Same shape as app/api/conversations.py's _serialize_message — kept as
    # its own copy rather than importing that module's private helper across
    # unrelated routers, but intentionally identical so the frontend's one
    # Message type already covers both.
    return {
        "id": str(message.id),
        "direction": message.direction,
        "body": message.body,
        "type": message.type,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
    }


@router.post("/playground/message")
@limiter.limit(lambda: settings.rate_limit_demo_chat)
def playground_message(
    request: Request,
    payload: PlaygroundMessageRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Message is required")

    response, retrieved, body, tool_outcome = playground_reply(db, principal.business_id, message)
    return {
        "data": {
            "reply": body,
            "model": response.model,
            "retrieved": [
                {"id": str(entry.id), "title": entry.title, "content": entry.content}
                for entry in retrieved
            ],
            "tool": tool_outcome,
        }
    }


@router.get("/playground/history")
def playground_history(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    """The Demo Chat conversation's persisted messages, oldest first — lets
    the frontend restore the transcript after a refresh instead of the local-
    only React state it previously relied on. Reuses the exact same
    get-or-create + tenant-implicit lookup `playground_reply` already uses;
    no new data-access path."""
    conversation = get_or_create_playground_conversation(db, principal.business_id)
    db.commit()  # durably persist a first-ever synthetic Customer/Conversation

    messages = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at)
    ).all()
    return {
        "data": {
            "conversation_id": str(conversation.id),
            "messages": [_serialize_playground_message(m) for m in messages],
        }
    }
