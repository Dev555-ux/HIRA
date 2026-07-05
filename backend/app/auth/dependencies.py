"""Authentication dependencies for protected dashboard/API routes.

`get_current_principal` is the guard every dashboard route depends on: it
verifies the Clerk JWT, resolves the Clerk user to a local User row, and returns
a Principal carrying the `business_id` used for tenant scoping. No token, an
invalid token, or an unknown user -> 401.

The token verifier is injected (overridable in tests) so routes can be tested
without a live Clerk account.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.clerk import verify_clerk_token
from app.db.session import get_db
from app.models import User


@dataclass
class Principal:
    user_id: uuid.UUID
    business_id: uuid.UUID
    clerk_user_id: str
    role: str


def get_token_verifier() -> Callable[[str], dict]:
    """Returns the callable that verifies a token and returns claims. Overridable in tests."""
    return verify_clerk_token


def get_verified_clerk_user_id(
    request: Request,
    verify: Callable[[str], dict] = Depends(get_token_verifier),
) -> str:
    """Verify the bearer token and return the Clerk user id (JWT `sub`).

    Unlike `get_current_principal`, this does *not* require a matching local
    `User` row — it's the dependency onboarding routes use, since a
    just-signed-up user has a valid Clerk session but no `User`/`Business` yet.
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth.removeprefix("Bearer ").strip()
    claims = verify(token)  # raises HTTPException(401) on failure

    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        )
    return clerk_user_id


def get_current_principal(
    clerk_user_id: str = Depends(get_verified_clerk_user_id),
    db: Session = Depends(get_db),
) -> Principal:
    user = db.scalars(select(User).where(User.clerk_user_id == clerk_user_id)).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    return Principal(
        user_id=user.id,
        business_id=user.business_id,
        clerk_user_id=clerk_user_id,
        role=user.role,
    )
