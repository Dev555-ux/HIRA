"""Authenticated dashboard API (/api/v1).

Every route here is protected by `get_current_principal` (Clerk JWT -> Principal
with business_id). All queries are scoped to the caller's business, so
cross-tenant data is never exposed: a message belonging to another business is
indistinguishable from a non-existent one (404).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenant import tenant_query
from app.models import Message
from app.services.messaging import WhatsAppSendError, send_text
from app.services.replies import approve_and_send

router = APIRouter(prefix="/api/v1", tags=["dashboard"])


def get_reply_sender():
    """The WhatsApp sender used when approving a reply. Overridable in tests."""
    return send_text


@router.get("/pending")
def list_pending(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    stmt = (
        tenant_query(Message, principal.business_id)
        .where(Message.direction == "outbound", Message.status == "pending_approval")
        .order_by(Message.created_at)
    )
    rows = db.scalars(stmt).all()
    return {
        "data": [
            {
                "id": str(m.id),
                "conversation_id": str(m.conversation_id),
                "body": m.body,
                "created_at": m.created_at.isoformat(),
            }
            for m in rows
        ]
    }


@router.post("/messages/{message_id}/approve")
def approve_message(
    message_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    sender=Depends(get_reply_sender),
) -> dict:
    try:
        message = approve_and_send(db, principal.business_id, message_id, sender=sender)
    except ValueError as exc:
        # Not this business's pending message (or doesn't exist). Don't reveal which.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from exc
    except WhatsAppSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to send reply"
        ) from exc
    return {"data": {"id": str(message.id), "status": message.status}}
