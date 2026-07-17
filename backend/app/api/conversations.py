"""Conversations API (/api/v1/conversations) — the Inbox backend.

Lists conversations (paginated, searchable by customer name/phone, filterable
by status), and exposes a single conversation's detail and message thread.
Every route sits behind `get_current_principal` and every query is
tenant-scoped via `tenant_query`/`get_scoped`, same as dashboard.py and
knowledge_base.py — a business can only ever see its own conversations.

Filter semantics (query param `status`):
- "open"    -> Conversation.status == "active"
- "closed"  -> Conversation.status == "closed"
- "pending" -> conversations with at least one outbound message still
               awaiting approval (Message.status == "pending_approval"). This
               is a derived, cross-cutting view, not a Conversation.status
               value, so it can overlap with "open" in practice.
Omitting `status` returns every conversation regardless of status (including
"escalated", which has no dedicated filter chip yet — see documentation/API.md).
"""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.ai.playground import PLAYGROUND_PHONE
from app.auth.dependencies import Principal, get_current_principal
from app.db.session import get_db
from app.db.tenant import get_scoped
from app.models import Conversation, Customer, Message

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])

StatusFilter = Literal["open", "pending", "closed"]
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_MESSAGE_LIMIT = 50
MAX_MESSAGE_LIMIT = 200


def _latest_message_previews(db: Session, conversation_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """One row per conversation: the body of its most recent message."""
    if not conversation_ids:
        return {}
    stmt = (
        select(Message.conversation_id, Message.body)
        .where(Message.conversation_id.in_(conversation_ids))
        .order_by(Message.conversation_id, Message.created_at.desc())
        .distinct(Message.conversation_id)
    )
    return {row.conversation_id: row.body for row in db.execute(stmt).all()}


def _conversation_ids_with_pending(db: Session, conversation_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    if not conversation_ids:
        return set()
    stmt = (
        select(Message.conversation_id)
        .where(
            Message.conversation_id.in_(conversation_ids),
            Message.direction == "outbound",
            Message.status == "pending_approval",
        )
        .distinct()
    )
    return set(db.scalars(stmt).all())


def _serialize_summary(
    conversation: Conversation, customer: Customer, preview: str | None, has_pending: bool
) -> dict:
    return {
        "id": str(conversation.id),
        "status": conversation.status,
        "customer": {
            "id": str(customer.id),
            "display_name": customer.display_name,
            "wa_phone": customer.wa_phone,
        },
        "last_message_at": (
            conversation.last_message_at.isoformat() if conversation.last_message_at else None
        ),
        "preview": preview,
        "has_pending_approval": has_pending,
        "created_at": conversation.created_at.isoformat(),
    }


def _serialize_message(message: Message) -> dict:
    return {
        "id": str(message.id),
        "direction": message.direction,
        "body": message.body,
        "type": message.type,
        "status": message.status,
        "created_at": message.created_at.isoformat(),
    }


@router.get("")
def list_conversations(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, min_length=1, max_length=200),
    status_filter: StatusFilter | None = Query(default=None, alias="status"),
    limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0),
) -> dict:
    stmt = (
        select(Conversation, Customer)
        .join(Customer, Customer.id == Conversation.customer_id)
        .where(Conversation.business_id == principal.business_id)
        .where(Customer.wa_phone != PLAYGROUND_PHONE)
    )

    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(Customer.display_name.ilike(like), Customer.wa_phone.ilike(like)))

    if status_filter == "open":
        stmt = stmt.where(Conversation.status == "active")
    elif status_filter == "closed":
        stmt = stmt.where(Conversation.status == "closed")
    elif status_filter == "pending":
        stmt = stmt.where(
            exists(
                select(Message.id).where(
                    Message.conversation_id == Conversation.id,
                    Message.direction == "outbound",
                    Message.status == "pending_approval",
                )
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))

    stmt = (
        stmt.order_by(Conversation.last_message_at.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()

    conversation_ids = [conv.id for conv, _ in rows]
    previews = _latest_message_previews(db, conversation_ids)
    pending_ids = _conversation_ids_with_pending(db, conversation_ids)

    data = [
        _serialize_summary(conv, cust, previews.get(conv.id), conv.id in pending_ids)
        for conv, cust in rows
    ]
    return {"data": data, "meta": {"total": total, "limit": limit, "offset": offset}}


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    conversation = get_scoped(db, Conversation, principal.business_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    customer = db.get(Customer, conversation.customer_id)
    previews = _latest_message_previews(db, [conversation.id])
    pending_ids = _conversation_ids_with_pending(db, [conversation.id])
    return {
        "data": _serialize_summary(
            conversation, customer, previews.get(conversation.id), conversation.id in pending_ids
        )
    }


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_MESSAGE_LIMIT, ge=1, le=MAX_MESSAGE_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict:
    conversation = get_scoped(db, Conversation, principal.business_id, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    total = db.scalar(
        select(func.count()).select_from(
            select(Message.id).where(Message.conversation_id == conversation_id).subquery()
        )
    )
    # Most recent `limit` messages (respecting `offset` to page further back),
    # then reversed to oldest-first for display — same convention as
    # app/ai/orchestrator.py's _load_history.
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    rows = list(reversed(rows))

    return {
        "data": [_serialize_message(m) for m in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }
