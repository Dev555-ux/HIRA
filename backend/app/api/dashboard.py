"""Authenticated dashboard API (/api/v1).

Every route here is protected by `get_current_principal` (Clerk JWT -> Principal
with business_id). All queries are scoped to the caller's business, so
cross-tenant data is never exposed: a message belonging to another business is
indistinguishable from a non-existent one (404).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.llm import LLMError
from app.api.calendar import map_calendar_error
from app.api.review_metadata import review_metadata_for
from app.auth.dependencies import Principal, get_current_principal
from app.calendar.providers.base import CalendarError
from app.core.time import to_iso_utc
from app.db.session import get_db
from app.db.tenant import tenant_query
from app.models import Conversation, Customer, Message
from app.services.messaging import WhatsAppNotConnectedError, WhatsAppSendError
from app.services.execution_traces import list_activity_for_dashboard
from app.services.messaging_service import MessagingService, WhatsAppWindowExpiredError
from app.services.replies import (
    escalate_reply,
    regenerate_draft,
    reject_reply,
    update_draft,
)

router = APIRouter(prefix="/api/v1", tags=["dashboard"])

# WhatsApp Cloud API's text message body limit — the same boundary the
# eventual send (via ChannelManager -> WhatsAppProvider) will hit, so an
# edited draft is validated against it up front.
MAX_DRAFT_LENGTH = 4096

# Sprint 36: cap on /pending so a business with a huge backlog can't force an
# unbounded query. Set high (not the 20/100 convention list_conversations/etc.
# use) deliberately — this is a guard rail against a truly unbounded scan, not
# a UX pagination feature yet (the frontend doesn't page through this list),
# so today's "see everything" behavior is preserved for any realistic backlog.
DEFAULT_PENDING_LIMIT = 200
MAX_PENDING_LIMIT = 200

# Sprint 84 (Dashboard Foundation): the Home "AI activity" feed only ever
# shows a handful of most-recent rows — unlike /pending, this is a narrative
# preview, not a backlog a business needs to see every row of.
DEFAULT_ACTIVITY_LIMIT = 20
MAX_ACTIVITY_LIMIT = 50


class MediaAttachmentRequest(BaseModel):
    """One `Message.media` entry — the same shape as
    `app.channels.base.message.MediaRef`, serialized. `kind` is validated
    against the channel-neutral `Capability`-backed set this platform
    models (see `app.channels.base.message.MediaKind`); whether the
    conversation's specific channel actually supports it is a send-time
    concern (graceful `DeliveryReceipt` failure), not a draft-edit-time one
    — see `update_draft()`'s docstring."""

    kind: Literal["image", "video", "audio", "document"]
    url: str
    mime_type: str | None = None
    caption: str | None = None


class UpdateDraftRequest(BaseModel):
    body: str
    # Sprint 65 PR 6: omitted/`null` leaves existing media untouched; `[]`
    # clears it. See `update_draft()`'s docstring.
    media: list[MediaAttachmentRequest] | None = None


def get_reply_sender():
    """The WhatsApp sender override used when approving a reply. Overridable
    in tests via `app.dependency_overrides[get_reply_sender]`. `None` in
    production means `MessagingService.approve_and_send()` uses its own
    default (`ChannelManager` -> the channel registry -> WhatsAppProvider,
    Sprint 64A PR 6/7) rather than calling the Graph API directly; it still
    raises WhatsAppSendError on any failure, so the WhatsAppSendError -> 502
    mapping in approve_message below is unchanged.
    """
    return None


def _customers_by_conversation(
    db: Session, conversation_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Customer]:
    if not conversation_ids:
        return {}
    rows = db.execute(
        select(Conversation.id, Customer)
        .join(Customer, Customer.id == Conversation.customer_id)
        .where(Conversation.id.in_(conversation_ids))
    ).all()
    return {row[0]: row[1] for row in rows}


def _last_inbound_previews(db: Session, conversation_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """One row per conversation: the body of its most recent inbound (customer) message."""
    if not conversation_ids:
        return {}
    stmt = (
        select(Message.conversation_id, Message.body)
        .where(Message.conversation_id.in_(conversation_ids), Message.direction == "inbound")
        .order_by(Message.conversation_id, Message.created_at.desc())
        .distinct(Message.conversation_id)
    )
    return {row.conversation_id: row.body for row in db.execute(stmt).all()}


def _serialize_customer(customer: Customer | None) -> dict | None:
    if customer is None:
        return None
    return {
        "id": str(customer.id),
        "display_name": customer.display_name,
        "wa_phone": customer.wa_phone,
    }


@router.get("/pending")
def list_pending(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_PENDING_LIMIT, ge=1, le=MAX_PENDING_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict:
    base_stmt = tenant_query(Message, principal.business_id).where(
        Message.direction == "outbound", Message.status == "pending_approval"
    )
    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    stmt = base_stmt.order_by(Message.created_at).limit(limit).offset(offset)
    rows = db.scalars(stmt).all()

    conversation_ids = [m.conversation_id for m in rows]
    customers = _customers_by_conversation(db, conversation_ids)
    previews = _last_inbound_previews(db, conversation_ids)

    return {
        "data": [
            {
                "id": str(m.id),
                "conversation_id": str(m.conversation_id),
                "body": m.body,
                "media": m.media or [],
                "created_at": to_iso_utc(m.created_at),
                "customer": _serialize_customer(customers.get(m.conversation_id)),
                "conversation_preview": previews.get(m.conversation_id),
                # AI review metadata (reply_id / confidence / grounding /
                # generation_status). Additive; existing fields unchanged.
                "review": review_metadata_for(m),
            }
            for m in rows
        ],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.get("/activity")
def list_activity(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_ACTIVITY_LIMIT, ge=1, le=MAX_ACTIVITY_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """Sprint 84 (Dashboard Foundation): the Home "AI activity" feed,
    replacing the frontend's old client-synthesized "Recent activity" —
    real execution_traces, read back as a narrative. See
    app/services/execution_traces.py::list_activity_for_dashboard."""
    return {
        "data": list_activity_for_dashboard(
            db, business_id=principal.business_id, limit=limit, offset=offset
        )
    }


@router.post("/messages/{message_id}/approve")
def approve_message(
    message_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    sender=Depends(get_reply_sender),
) -> dict:
    try:
        message = MessagingService(db).approve_and_send(
            principal.business_id, message_id, sender=sender
        )
    except ValueError as exc:
        # Not this business's pending message (or doesn't exist). Don't reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except CalendarError as exc:
        # A proposed calendar action (message.type == "tool_call") failed to
        # execute on approval — e.g. the slot was taken meanwhile (DEC-032).
        raise map_calendar_error(exc) from exc
    except WhatsAppNotConnectedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WhatsAppWindowExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WhatsAppSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to send reply"
        ) from exc
    return {"data": {"id": str(message.id), "status": message.status}}


@router.patch("/messages/{message_id}/draft")
def edit_draft(
    message_id: uuid.UUID,
    payload: UpdateDraftRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    body = payload.body.strip()
    if not body:
        raise HTTPException(status_code=422, detail="Draft body cannot be blank")
    if len(body) > MAX_DRAFT_LENGTH:
        raise HTTPException(
            status_code=422,
            detail=f"Draft body cannot exceed {MAX_DRAFT_LENGTH} characters",
        )

    media = (
        [m.model_dump() for m in payload.media] if payload.media is not None else None
    )
    try:
        message = update_draft(db, principal.business_id, message_id, body=body, media=media)
    except ValueError as exc:
        # Not this business's pending message, doesn't exist, or already approved —
        # indistinguishable, same as approve/reject/regenerate/escalate.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    return {
        "data": {
            "id": str(message.id),
            "body": message.body,
            "media": message.media or [],
            "status": message.status,
        }
    }


@router.post("/messages/{message_id}/reject")
def reject_message(
    message_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    try:
        message = reject_reply(db, principal.business_id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    return {"data": {"id": str(message.id), "status": message.status}}


@router.post("/messages/{message_id}/regenerate")
def regenerate_message(
    message_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    try:
        message = regenerate_draft(db, principal.business_id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except LLMError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to regenerate reply"
        ) from exc
    return {"data": {"id": str(message.id), "body": message.body, "status": message.status}}


@router.post("/messages/{message_id}/escalate")
def escalate_message(
    message_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    try:
        message, escalation = escalate_reply(db, principal.business_id, message_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    return {
        "data": {
            "id": str(message.id),
            "status": message.status,
            "escalation": {
                "id": str(escalation.id),
                "conversation_id": str(escalation.conversation_id),
                "reason": escalation.reason,
                "status": escalation.status,
                "created_at": to_iso_utc(escalation.created_at),
            },
        }
    }
