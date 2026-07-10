"""Clerk JWT verification.

Clerk issues RS256 session JWTs signed with keys published at a JWKS endpoint.
We verify the signature against that JWKS (public keys — no secret needed),
plus expiry and, if configured, issuer. Returns the token claims; raises
HTTPException(401) on any failure.
"""

from __future__ import annotations

import logging

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.core.config import settings

logger = logging.getLogger(__name__)

_jwks_client: PyJWKClient | None = None


def _client() -> PyJWKClient:
    global _jwks_client
    if not settings.clerk_jwks_url:
        logger.error(
            "CLERK_JWKS_URL is not set — every authenticated request will 500 "
            "until it's configured in this environment's variables."
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Clerk JWKS URL is not configured",
        )
    if _jwks_client is None:
        logger.info("Initializing Clerk JWKS client for %s", settings.clerk_jwks_url)
        _jwks_client = PyJWKClient(settings.clerk_jwks_url)
    return _jwks_client


def verify_clerk_token(token: str) -> dict:
    try:
        signing_key = _client().get_signing_key_from_jwt(token)
        kwargs: dict = {}
        if settings.clerk_issuer:
            kwargs["issuer"] = settings.clerk_issuer
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            **kwargs,
        )
    except HTTPException:
        raise
    except Exception as exc:  # invalid signature / expired / malformed / issuer mismatch / JWKS fetch failure
        logger.warning("Clerk token verification failed: %s: %s", type(exc).__name__, exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token"
        ) from exc
