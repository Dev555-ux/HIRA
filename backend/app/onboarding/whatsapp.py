"""WhatsApp number connection for the bootstrap service (Phase 1).

Repoints an existing business at a (possibly rotated) WhatsApp
phone_number_id, preserving the business's id and everything linked to it
(KB entries, conversations, messages). Not to be confused with
`app.services.messaging`, which sends messages — this module only manages
which phone_number_id a business is associated with.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Business
from app.onboarding.verification import find_business_by_any_phone_number_id


def connect_phone_number(
    db: Session,
    *,
    old_phone_number_id: str,
    new_phone_number_id: str,
    whatsapp_business_account_id: str,
    mode: str = "autonomous",
) -> Business:
    """Repoint a business at `new_phone_number_id`.

    Looks the business up by either the old or new id, so re-running after
    the update has already happened is a no-op. Raises `LookupError` if
    neither id matches any business.
    """
    business = find_business_by_any_phone_number_id(db, [old_phone_number_id, new_phone_number_id])
    if business is None:
        raise LookupError(
            "No business found with the old or new phone number id. "
            "Run scripts/seed_business.py first."
        )

    business.whatsapp_phone_number_id = new_phone_number_id
    business.whatsapp_business_account_id = whatsapp_business_account_id
    business.mode = mode
    db.commit()
    db.refresh(business)
    return business
