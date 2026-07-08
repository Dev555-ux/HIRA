"""Business identity provisioning for the bootstrap service (Phase 1).

Creates or updates the Business row keyed by WhatsApp phone_number_id. This is
the ops/dev counterpart to `app.services.provisioning`, which provisions a
Business from a live Clerk sign-up — this one is used for seeding or
re-seeding a business directly against WhatsApp identifiers.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Business
from app.onboarding.verification import find_business_by_phone_number_id


def create_or_update_business(
    db: Session,
    *,
    name: str,
    phone_number_id: str,
    whatsapp_business_account_id: str,
    mode: str = "autonomous",
) -> tuple[Business, str]:
    """Create a business wired to `phone_number_id`, or update it in place.

    Idempotent: re-running with the same `phone_number_id` updates the
    existing row (mode + WABA id only, matching prior seed-script behavior)
    rather than creating a duplicate. Returns (business, "created"|"updated").
    """
    business = find_business_by_phone_number_id(db, phone_number_id)
    if business is None:
        business = Business(
            name=name,
            whatsapp_phone_number_id=phone_number_id,
            whatsapp_business_account_id=whatsapp_business_account_id,
            mode=mode,
        )
        db.add(business)
        action = "created"
    else:
        business.mode = mode
        business.whatsapp_business_account_id = whatsapp_business_account_id
        action = "updated"

    db.commit()
    db.refresh(business)
    return business, action
