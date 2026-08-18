"""Instagram API (/api/v1/instagram) — Sprint 65 PR 2: the business
connection flow only. No messaging, no webhooks, no inbox — see
documentation/architecture/channel-development-guide.md and
app/channels/instagram/provider.py's module docstring for what's
deliberately not here yet.

Route shape mirrors app/api/calendar.py's OAuth routes (signed, single-use
state on a public GET callback with no Clerk session possible there) plus
one addition Calendar has no equivalent of: Instagram's callback can
discover more than one eligible Page, so a choices/finalize step sits
between callback and a stored connection whenever that happens — see
app/instagram/oauth.py's module docstring.
"""

from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.core.config import settings
from app.db.session import get_db
from app.instagram import credentials as instagram_credentials
from app.instagram import oauth
from app.instagram.errors import (
    InstagramAuthError,
    InstagramDuplicateConnectionError,
    InstagramError,
    InstagramNotConfiguredError,
    InstagramOAuthStateError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/instagram", tags=["instagram"])

# Selection/Page ids are short opaque strings, not human-typed text —
# bounded the same way app/api/whatsapp.py bounds its own request fields.
MAX_TOKEN_LENGTH = 512


def _map_error(exc: InstagramError) -> HTTPException:
    if isinstance(exc, InstagramNotConfiguredError):
        logger.warning("Instagram not configured: %s", exc)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Instagram connection isn't available on this deployment yet.",
        )
    if isinstance(exc, InstagramDuplicateConnectionError):
        logger.warning("Instagram connect blocked, account already connected elsewhere: %s", exc)
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, InstagramAuthError):
        logger.warning("Instagram Meta API call failed: %s", exc)
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Couldn't complete the Instagram connection. Please try again.",
        )
    logger.warning("Unhandled Instagram error: %s", exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Something went wrong connecting Instagram. Please try again.",
    )


def _redirect_to_frontend(status_value: str, **params: str | None) -> RedirectResponse:
    query = {"instagram": status_value, **{k: v for k, v in params.items() if v}}
    return RedirectResponse(url=f"{settings.frontend_url}/instagram?{urlencode(query)}")


class FinalizeConnectionRequest(BaseModel):
    selection_token: str = Field(min_length=1, max_length=MAX_TOKEN_LENGTH)
    page_id: str = Field(min_length=1, max_length=MAX_TOKEN_LENGTH)


def _serialize_choice(choice: oauth.InstagramConnectionChoice) -> dict:
    return {
        "page_id": choice.page_id,
        "page_name": choice.page_name,
        "instagram_business_account_id": choice.instagram_business_account_id,
        "instagram_username": choice.instagram_username,
    }


@router.get("/oauth/connect")
def start_oauth_connect(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    try:
        authorization_url = oauth.build_authorization_url(db, principal.business_id)
    except InstagramError as exc:
        raise _map_error(exc) from exc
    # business_id only — never the state param (it's a signed credential-
    # adjacent token) or the authorization_url (carries that same state as
    # a query param).
    logger.info("Instagram OAuth connect initiated for business %s", principal.business_id)
    return {"data": {"authorization_url": authorization_url}}


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Meta redirects the user's browser here directly after consent — no
    Clerk session is possible. The signed, single-use `state` param
    authenticates this request instead, recovering which business initiated
    the connect."""
    if error:
        return _redirect_to_frontend("error", message=error)
    if not code or not state:
        return _redirect_to_frontend("error", message="Missing authorization code")

    try:
        attempt = oauth.verify_and_consume_state(db, state)
    except InstagramOAuthStateError as exc:
        logger.warning("Instagram OAuth callback rejected: %s", exc)
        return _redirect_to_frontend("error", message="Invalid or expired connection request")

    try:
        user_access_token = oauth.exchange_code_for_user_token(code)
        choices = oauth.discover_connectable_pages(user_access_token)
    except InstagramAuthError as exc:
        logger.warning(
            "Instagram OAuth exchange failed for business %s: %s", attempt.business_id, exc
        )
        return _redirect_to_frontend(
            "error", message="Couldn't connect Instagram. Please try again."
        )

    if not choices:
        return _redirect_to_frontend(
            "error", message="No Instagram professional account found on any of your Pages."
        )

    if len(choices) == 1:
        choice = choices[0]
        try:
            instagram_credentials.store_credentials(
                db,
                attempt.business_id,
                page_id=choice.page_id,
                page_access_token=choice.page_access_token,
                instagram_business_account_id=choice.instagram_business_account_id,
                instagram_username=choice.instagram_username,
            )
        except InstagramDuplicateConnectionError as exc:
            logger.warning(
                "Instagram connect blocked, account already connected elsewhere: %s", exc
            )
            return _redirect_to_frontend("error", message=str(exc))
        # "connected" covers both a first connect and a reconnect — store_
        # credentials() is the same idempotent create-or-replace path for
        # both (see its own docstring); no separate reconnect codepath
        # exists to log differently. page_id/IG account id only, never the
        # page access token.
        logger.info(
            "Instagram connected for business %s (page_id=%s, ig_account_id=%s)",
            attempt.business_id,
            choice.page_id,
            choice.instagram_business_account_id,
        )
        return _redirect_to_frontend("connected")

    # Multiple eligible Pages — do not automatically select one (Sprint 65
    # PR 2 requirement). Hand the frontend an opaque selection_token instead
    # of the raw choice list; it fetches the list itself via
    # GET /connect/choices under its own Clerk session.
    selection_token = oauth.store_pending_choices(db, attempt, user_access_token)
    return _redirect_to_frontend("choose", selection_token=selection_token)


@router.get("/connect/choices")
def get_connect_choices(
    selection_token: str = Query(..., min_length=1, max_length=MAX_TOKEN_LENGTH),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    attempt = oauth.get_pending_attempt(db, principal.business_id, selection_token)
    if attempt is None:
        raise HTTPException(status_code=404, detail="No pending Instagram connection found")

    try:
        choices = oauth.discover_connectable_pages(oauth.decrypt_pending_token(attempt))
    except InstagramAuthError as exc:
        raise _map_error(exc) from exc

    return {"data": {"choices": [_serialize_choice(choice) for choice in choices]}}


@router.post("/connect/finalize")
def finalize_connection(
    payload: FinalizeConnectionRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    attempt = oauth.get_pending_attempt(db, principal.business_id, payload.selection_token)
    if attempt is None:
        raise HTTPException(status_code=404, detail="No pending Instagram connection found")

    try:
        choices = oauth.discover_connectable_pages(oauth.decrypt_pending_token(attempt))
    except InstagramAuthError as exc:
        raise _map_error(exc) from exc

    choice = next((c for c in choices if c.page_id == payload.page_id), None)
    if choice is None:
        raise HTTPException(status_code=422, detail="That Page is no longer a valid choice")

    try:
        credential = instagram_credentials.store_credentials(
            db,
            principal.business_id,
            page_id=choice.page_id,
            page_access_token=choice.page_access_token,
            instagram_business_account_id=choice.instagram_business_account_id,
            instagram_username=choice.instagram_username,
        )
    except InstagramDuplicateConnectionError as exc:
        raise _map_error(exc) from exc

    oauth.consume_pending_attempt(db, attempt)
    logger.info(
        "Instagram connected for business %s (page_id=%s, ig_account_id=%s)",
        principal.business_id,
        choice.page_id,
        choice.instagram_business_account_id,
    )
    return {"data": {"connected": True, "instagram_username": credential.instagram_username}}


@router.get("/status")
def get_instagram_status(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    credential = instagram_credentials.get_stored_credential(db, principal.business_id)
    if credential is None:
        return {"data": {"connected": False, "status": "disconnected", "instagram_username": None}}

    try:
        health = instagram_credentials.check_connection_health(credential)
    except InstagramAuthError as exc:
        # A network blip isn't evidence the connection itself is broken —
        # report the last-known status rather than fail the whole request.
        logger.warning(
            "Instagram health check unreachable for business %s, reporting last-known status: %s",
            principal.business_id,
            exc,
        )
        health = credential.connection_status

    if credential.connection_status != health:
        credential.connection_status = health
        db.commit()

    return {
        "data": {
            "connected": health == instagram_credentials.CONNECTED,
            "status": health,
            "instagram_username": credential.instagram_username,
        }
    }


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_instagram(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    was_connected = instagram_credentials.disconnect(db, principal.business_id)
    logger.info(
        "Instagram disconnect for business %s (was_connected=%s)",
        principal.business_id,
        was_connected,
    )
