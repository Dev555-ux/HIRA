"""Shared business-resolution helpers for the bootstrap service.

Every bootstrap operation (business provisioning, WhatsApp connection,
knowledge seeding) needs to find "the target business" from some identifier.
This is the single place that lookup logic lives, instead of each operation
re-implementing its own `select(Business)...`.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business


def find_business_by_phone_number_id(db: Session, phone_number_id: str) -> Business | None:
    """Look up a business by its WhatsApp phone_number_id.

    Same lookup the inbound webhook uses (app/webhooks/whatsapp.py).
    """
    return db.scalars(
        select(Business).where(Business.whatsapp_phone_number_id == phone_number_id)
    ).first()


def find_business_by_any_phone_number_id(
    db: Session, phone_number_ids: list[str]
) -> Business | None:
    """Look up a business matching any of several phone_number_ids.

    Used during a number rotation, where the business may still be keyed on
    the old id or may already have been updated to the new one.
    """
    return db.scalars(
        select(Business).where(Business.whatsapp_phone_number_id.in_(phone_number_ids))
    ).first()


def resolve_sole_or_by_phone_number_id(db: Session, phone_number_id: str | None) -> Business:
    """Resolve the target business for an operation with no explicit id.

    Rules (for ops/dev bootstrap scripts, not request-scoped API code, which
    always has an explicit tenant from auth):
      1. If there is exactly one Business row, use it.
      2. Otherwise, `phone_number_id` must be given and match one business.
      3. Otherwise, raise rather than guessing.
    """
    businesses = db.scalars(select(Business)).all()
    if len(businesses) == 1:
        return businesses[0]

    if phone_number_id:
        business = find_business_by_phone_number_id(db, phone_number_id)
        if business is None:
            raise LookupError(
                f"No business found with whatsapp_phone_number_id={phone_number_id!r}."
            )
        return business

    if not businesses:
        raise LookupError("No business found. Run scripts/seed_business.py first.")

    candidates = ", ".join(repr(b.whatsapp_phone_number_id) for b in businesses)
    raise LookupError(
        "Multiple businesses found; set PHONE_NUMBER_ID to disambiguate "
        f"(candidates: {candidates})."
    )
