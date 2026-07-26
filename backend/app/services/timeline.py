"""Aggregates a customer's Message history and Lead activity into one
chronological timeline (newest-first), for the Customer detail page.

Message and LeadEvent don't share a column signature, so this merges two
independent, newest-first, `offset + limit`-bounded queries in Python rather
than a SQL UNION ALL across mismatched/nullable-placeholder columns — the
simpler option at MVP data volumes. See DEC-031.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import to_iso_utc
from app.models import Conversation, Lead, LeadEvent, Message


def _serialize_message(message: Message) -> dict:
    return {
        "type": "message",
        "id": str(message.id),
        "created_at": to_iso_utc(message.created_at),
        "direction": message.direction,
        "body": message.body,
        "status": message.status,
    }


def _serialize_lead_event(event: LeadEvent) -> dict:
    return {
        "type": "lead_event",
        "id": str(event.id),
        "created_at": to_iso_utc(event.created_at),
        "event_type": event.type,
        "from_value": event.from_value,
        "to_value": event.to_value,
        "note": event.note,
    }


def get_customer_timeline(
    db: Session,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Newest-first, merged Message + LeadEvent history for one customer.

    Tenant-scoped: messages are reached only through this business's own
    conversations for this customer; the lead (and its events) only through
    `Lead.business_id` — `LeadEvent` has no `business_id` column of its own.
    """
    fetch = offset + limit

    conversation_ids = db.scalars(
        select(Conversation.id).where(
            Conversation.business_id == business_id, Conversation.customer_id == customer_id
        )
    ).all()

    message_total = 0
    messages: list[Message] = []
    if conversation_ids:
        message_total = db.scalar(
            select(func.count(Message.id)).where(Message.conversation_id.in_(conversation_ids))
        )
        messages = db.scalars(
            select(Message)
            .where(Message.conversation_id.in_(conversation_ids))
            .order_by(Message.created_at.desc())
            .limit(fetch)
        ).all()

    lead = db.scalars(
        select(Lead).where(Lead.business_id == business_id, Lead.customer_id == customer_id)
    ).first()

    lead_event_total = 0
    lead_events: list[LeadEvent] = []
    if lead is not None:
        lead_event_total = db.scalar(
            select(func.count(LeadEvent.id)).where(LeadEvent.lead_id == lead.id)
        )
        lead_events = db.scalars(
            select(LeadEvent)
            .where(LeadEvent.lead_id == lead.id)
            .order_by(LeadEvent.created_at.desc())
            .limit(fetch)
        ).all()

    merged = sorted([*messages, *lead_events], key=lambda row: row.created_at, reverse=True)
    page = merged[offset : offset + limit]

    items = [
        _serialize_message(row) if isinstance(row, Message) else _serialize_lead_event(row)
        for row in page
    ]
    return items, message_total + lead_event_total
