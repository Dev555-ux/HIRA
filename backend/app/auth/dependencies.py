"""Authentication dependencies for protected dashboard/API routes.

`get_current_principal` is the guard every dashboard route depends on: it
verifies the Clerk JWT, resolves the Clerk user to a local User row, and returns
a Principal carrying the `business_id` used for tenant scoping. No token, an
invalid token, or an unknown user -> 401.

The token verifier is injected (overridable in tests) so routes can be tested
without a live Clerk account.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.clerk import verify_clerk_token
from app.core.config import settings
from app.core.monitoring import set_business_context
from app.db.session import get_db
from app.models import User

logger = logging.getLogger(__name__)

MOCK_TOKEN = "dev-mock-token"
MOCK_CLERK_USER_ID = "dev-mock-user"


@dataclass
class Principal:
    user_id: uuid.UUID
    business_id: uuid.UUID
    clerk_user_id: str
    role: str


def _verify_mock_token(token: str) -> dict:
    if token != MOCK_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        )
    return {"sub": MOCK_CLERK_USER_ID}


def get_token_verifier() -> Callable[[str], dict]:
    """Returns the callable that verifies a token and returns claims. Overridable in tests.

    Falls back to a fixed dev identity (accepting only the literal token
    "dev-mock-token") when Clerk isn't configured and `ALLOW_MOCK_AUTH` is
    explicitly set — mirrors the frontend's mock auth, which sends this same
    token when it has no Clerk publishable key. With Clerk unconfigured and
    `ALLOW_MOCK_AUTH` unset (the default), requests still fail loudly via
    `verify_clerk_token` rather than silently being treated as authenticated.
    """
    if not settings.clerk_jwks_url and settings.allow_mock_auth:
        return _verify_mock_token
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
        logger.info("%s %s: missing bearer token", request.method, request.url.path)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = auth.removeprefix("Bearer ").strip()
    claims = verify(token)  # raises HTTPException(401/500) on failure

    clerk_user_id = claims.get("sub")
    if not clerk_user_id:
        logger.warning("%s %s: verified token has no 'sub' claim", request.method, request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        )
    return clerk_user_id


def get_current_principal(
    request: Request,
    clerk_user_id: str = Depends(get_verified_clerk_user_id),
    db: Session = Depends(get_db),
) -> Principal:
    user = db.scalars(select(User).where(User.clerk_user_id == clerk_user_id)).first()
    if user is None:
        logger.info("No User row for clerk_user_id=%s", clerk_user_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown user")

    # Every protected route depends on this function, making it the one place
    # that can know business_id early enough for app.core.request_logging's
    # per-request log line to include it — that middleware sees only
    # `request.state`, not route dependencies. Also tags Sentry (a no-op if
    # SENTRY_DSN isn't set — see app/core/monitoring.py).
    request.state.business_id = str(user.business_id)
    set_business_context(str(user.business_id))

    return Principal(
        user_id=user.id,
        business_id=user.business_id,
        clerk_user_id=clerk_user_id,
        role=user.role,
    )


def _founder_clerk_user_ids() -> set[str]:
    return {s.strip() for s in settings.founder_clerk_user_ids.split(",") if s.strip()}


def get_founder_principal(clerk_user_id: str = Depends(get_verified_clerk_user_id)) -> str:
    """Sprint 73: guards the internal, cross-tenant Founder Operations
    Dashboard (`app/api/founder_ops.py`). Deliberately built on
    `get_verified_clerk_user_id` (authenticate only), not
    `get_current_principal` (authenticate + resolve one business) — this
    view is explicitly *not* scoped to a single business, so there's no
    single `business_id` to resolve.

    Checked against `settings.founder_clerk_user_ids`, not `User.role`:
    every business owner already has `role="owner"` (the only role any
    signup flow ever sets — see app/services/provisioning.py), so branching
    on role would let every customer see every other business's data, not
    just the founder. A 404 (not 403) for a non-allowlisted caller, matching
    this codebase's existing convention of not confirming a resource's
    existence to someone not entitled to see it (documentation/API.md's
    cross-tenant rule) — a business owner probing this URL learns nothing
    from the response.
    """
    if clerk_user_id not in _founder_clerk_user_ids():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return clerk_user_id
