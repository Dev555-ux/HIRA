"""Dev convenience: point the mock-auth dev user at a given business by name.

Mock auth (`app/auth/dependencies.py`, active when Clerk isn't configured)
always resolves to a single fixed Clerk user id (`dev-mock-user`), which maps
to exactly one `User` row -> one `business_id`. That's normally your own
day-to-day dev business — but to actually show scripts/seed_demo_workspace.py's
"Bright Smile Dental Studio" workspace in a browser (rather than just in the
database), this script repoints that one User row at it, and back again
afterward.

Idempotent and non-destructive: it only ever updates the existing
dev-mock-user's business_id (creating the User row on first use), never
creates or deletes a Business. Run from the backend/ directory:

    .venv/bin/python scripts/use_demo_business.py "Bright Smile Dental Studio"
    .venv/bin/python scripts/use_demo_business.py "stoneveil"   # switch back
    .venv/bin/python scripts/use_demo_business.py               # list businesses
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.auth.dependencies import MOCK_CLERK_USER_ID
from app.db.session import SessionLocal
from app.models import Business, User


def main() -> None:
    db = SessionLocal()
    try:
        if len(sys.argv) < 2:
            businesses = db.scalars(select(Business).order_by(Business.name)).all()
            current = db.scalars(
                select(User).where(User.clerk_user_id == MOCK_CLERK_USER_ID)
            ).first()
            print("Businesses:")
            for b in businesses:
                marker = " <- current mock-auth business" if current and current.business_id == b.id else ""
                print(f"  {b.name!r} ({b.id}){marker}")
            print('\nUsage: .venv/bin/python scripts/use_demo_business.py "<business name>"')
            return

        name = sys.argv[1]
        business = db.scalars(select(Business).where(Business.name == name)).first()
        if business is None:
            raise SystemExit(f"No business named {name!r} — run with no arguments to list them.")

        user = db.scalars(select(User).where(User.clerk_user_id == MOCK_CLERK_USER_ID)).first()
        if user is None:
            user = User(
                business_id=business.id,
                clerk_user_id=MOCK_CLERK_USER_ID,
                email="dev@example.com",
                role="owner",
            )
            db.add(user)
            print(f"Created dev-mock-user, pointed at {name!r}")
        else:
            previous = db.get(Business, user.business_id)
            user.business_id = business.id
            print(f"Switched dev-mock-user from {previous.name if previous else '(none)'!r} to {name!r}")
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
