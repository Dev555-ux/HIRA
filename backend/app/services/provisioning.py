"""Turns an authenticated Clerk identity into a HIRA tenant.

Until now, the only way a `Business` + `User` pair came into existence was a
developer running `scripts/seed_business.py` by hand. This is the self-service
replacement: called once, from the onboarding flow, right after a Clerk
sign-up. See ONBOARDING_ARCHITECTURE.md §4.2.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Business, User


def get_business_for_clerk_user(db: Session, clerk_user_id: str) -> Business | None:
    """Return the business the given Clerk identity already belongs to, if any."""
    user = db.scalars(select(User).where(User.clerk_user_id == clerk_user_id)).first()
    if user is None:
        return None
    return db.get(Business, user.business_id)


def provision_business(
    db: Session,
    *,
    clerk_user_id: str,
    owner_email: str,
    name: str,
    industry: str | None = None,
    contact_email: str | None = None,
    country: str | None = None,
    timezone: str | None = None,
) -> Business:
    """Create a Business + its owner User for this Clerk identity.

    Idempotent: if a User already exists for `clerk_user_id`, returns their
    existing business rather than creating a second one — safe to call again
    if the onboarding request is retried (e.g. a flaky network on submit).
    """
    existing = get_business_for_clerk_user(db, clerk_user_id)
    if existing is not None:
        return existing

    business = Business(
        name=name,
        vertical=industry,
        contact_email=contact_email,
        country=country,
        timezone=timezone or "UTC",
    )
    db.add(business)
    db.flush()  # assign business.id before the User row references it

    user = User(business_id=business.id, clerk_user_id=clerk_user_id, email=owner_email, role="owner")
    db.add(user)
    db.commit()
    db.refresh(business)
    return business
