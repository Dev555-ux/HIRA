"""Lead pipeline actions: create, update, delete.

Every function is tenant-scoped by `business_id` via `get_scoped`, matching
`app/services/replies.py`'s convention. Each write that represents real
pipeline activity (stage, notes, next_follow_up_at, assigned_to — but not
source/estimated_value, treated as descriptive attributes) also appends a
`LeadEvent` row, and only when the value actually changes. See DEC-031.

`LeadEvent` has no `business_id` of its own, so anything that queries it
directly (see `app/services/timeline.py`) must join through `Lead` to stay
tenant-scoped — never `tenant_query`/`get_scoped` on `LeadEvent` itself.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.tenant import get_scoped
from app.models import Customer, Lead, LeadEvent, User

logger = logging.getLogger(__name__)

# Fields whose changes are timeline-worthy activity, mapped to their LeadEvent
# type. source/estimated_value are deliberately excluded (DEC-031).
_EVENT_FIELDS = {
    "stage": "stage_change",
    "notes": "notes_updated",
    "next_follow_up_at": "follow_up_set",
    "assigned_to": "assigned",
}


class LeadNotFoundError(Exception):
    """The lead doesn't exist, or doesn't belong to this business."""


class CustomerNotFoundError(Exception):
    """The referenced customer doesn't exist, or doesn't belong to this business."""


class LeadAlreadyExistsError(Exception):
    """This business already has a lead for this customer (UNIQUE(business_id, customer_id))."""


class InvalidAssigneeError(Exception):
    """assigned_to doesn't reference a user of this business."""


def _normalize_follow_up(value: datetime | None) -> datetime | None:
    """Store next_follow_up_at as a naive UTC timestamp, matching every other
    DateTime column in this schema (created_at, resolved_at, window_expires_at)."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _stringify(value: Any) -> str | None:
    """Render a field value as the plain string LeadEvent.from_value/to_value store."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _validate_assignee(db: Session, business_id: uuid.UUID, assigned_to: uuid.UUID | None) -> None:
    if assigned_to is None:
        return
    if get_scoped(db, User, business_id, assigned_to) is None:
        raise InvalidAssigneeError("assigned_to must be a user of this business")


def get_lead_for_customer(
    db: Session, business_id: uuid.UUID, customer_id: uuid.UUID
) -> Lead | None:
    """This customer's lead, if one exists. One lead per (business, customer)
    for the MVP (DEC-031) — never more than one row to choose between.

    Shared by create_lead's existence check, app/ai/lead_tools.py, and
    app/ai/context.py (DEC-034) — the one place this query lives.
    """
    return db.scalars(
        select(Lead).where(Lead.business_id == business_id, Lead.customer_id == customer_id)
    ).first()


def create_lead(
    db: Session,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    *,
    stage: str = "new",
    source: str | None = None,
    estimated_value: float | None = None,
    notes: str | None = None,
    next_follow_up_at: datetime | None = None,
    assigned_to: uuid.UUID | None = None,
) -> Lead:
    """Create a lead for a customer. Raises CustomerNotFoundError,
    LeadAlreadyExistsError, or InvalidAssigneeError on invalid input."""
    if get_scoped(db, Customer, business_id, customer_id) is None:
        raise CustomerNotFoundError("Customer not found for this business")

    existing = get_lead_for_customer(db, business_id, customer_id)
    if existing is not None:
        raise LeadAlreadyExistsError("A lead already exists for this customer")

    _validate_assignee(db, business_id, assigned_to)

    lead = Lead(
        business_id=business_id,
        customer_id=customer_id,
        stage=stage,
        source=source,
        estimated_value=estimated_value,
        notes=notes,
        next_follow_up_at=_normalize_follow_up(next_follow_up_at),
        assigned_to=assigned_to,
    )
    db.add(lead)
    db.flush()
    db.add(LeadEvent(lead_id=lead.id, type="lead_created", to_value=stage))
    db.commit()
    db.refresh(lead)
    logger.info("Created lead %s for customer %s (business %s)", lead.id, customer_id, business_id)
    return lead


def update_lead(
    db: Session,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    updates: dict[str, Any],
) -> Lead:
    """Apply a partial update to a lead, logging a LeadEvent for each
    timeline-worthy field that actually changes. `updates` must contain only
    the fields the caller explicitly provided (see app/api/leads.py's
    `model_dump(exclude_unset=True)`), so an omitted field is left untouched
    and an explicit `null` clears a nullable one.

    Raises LeadNotFoundError or InvalidAssigneeError.
    """
    lead = get_scoped(db, Lead, business_id, lead_id)
    if lead is None:
        raise LeadNotFoundError("Lead not found for this business")

    if "assigned_to" in updates:
        _validate_assignee(db, business_id, updates["assigned_to"])
    if "next_follow_up_at" in updates:
        updates["next_follow_up_at"] = _normalize_follow_up(updates["next_follow_up_at"])

    events = []
    for field, value in updates.items():
        old_value = getattr(lead, field)
        setattr(lead, field, value)
        if field in _EVENT_FIELDS and old_value != value:
            events.append(
                LeadEvent(
                    lead_id=lead.id,
                    type=_EVENT_FIELDS[field],
                    from_value=_stringify(old_value),
                    to_value=_stringify(value),
                )
            )

    db.add_all(events)
    db.commit()
    db.refresh(lead)
    logger.info("Updated lead %s (business %s): %s", lead_id, business_id, sorted(updates))
    return lead


def delete_lead(db: Session, business_id: uuid.UUID, lead_id: uuid.UUID) -> bool:
    """Delete a lead (cascades to its LeadEvent history). Returns False if not found."""
    lead = get_scoped(db, Lead, business_id, lead_id)
    if lead is None:
        return False
    db.delete(lead)
    db.commit()
    logger.info("Deleted lead %s (business %s)", lead_id, business_id)
    return True
