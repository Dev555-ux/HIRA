"""Calendar API (/api/v1/calendar) — Sprint 29 (DEC-032).

Google OAuth connect/callback, connection status/disconnect, business
timezone + working-hours settings, and availability lookup. Every route
except the OAuth callback sits behind `get_current_principal`, same as every
other router. The callback is a Google browser redirect (no Clerk session
possible) authenticated instead by a signed `state` param — the same
signature-not-Bearer-token pattern the WhatsApp webhook already uses.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import Principal, get_current_principal
from app.calendar import credentials as calendar_credentials
from app.calendar import oauth
from app.calendar.factory import get_appointment_service
from app.calendar.oauth import OAuthStateError
from app.core.time import to_iso_utc
from app.core.timezones import validate_timezone
from app.calendar.providers.base import (
    CalendarAlreadyCancelledError,
    CalendarAuthError,
    CalendarConflictError,
    CalendarError,
    CalendarNotConfiguredError,
    CalendarNotConnectedError,
    CalendarNotFoundError,
    CalendarValidationError,
)
from app.core.config import settings
from app.db.session import get_db
from app.models import Business

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

_DAY_KEYS = {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}


def map_calendar_error(exc: CalendarError) -> HTTPException:
    """Shared CalendarError -> HTTPException mapping (also used by app/api/appointments.py)."""
    if isinstance(exc, CalendarNotConfiguredError):
        # CalendarNotConfiguredError's own message names the missing env var
        # (e.g. "GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET/... are not set") —
        # exactly what a developer needs, and exactly what a business owner
        # must never see. Logged here (once, at the point the client-facing
        # detail is decided) so the real detail isn't lost, then replaced
        # with a plain-language message for the response.
        logger.warning("Calendar not configured: %s", exc)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Calendar integration hasn't been configured yet.",
        )
    if isinstance(exc, (CalendarNotConnectedError, CalendarConflictError, CalendarAlreadyCancelledError)):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, CalendarValidationError):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if isinstance(exc, CalendarAuthError):
        # Unlike the two above, this one's message isn't always hand-authored
        # — app/calendar/oauth.py's token-exchange failure wraps whatever the
        # underlying oauthlib/google-auth exception says (Sprint 52B, Task 5).
        logger.warning("Calendar auth failed: %s", exc)
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Couldn't complete the Google Calendar connection. Please try again.",
        )
    if isinstance(exc, CalendarNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    # Any other CalendarError (e.g. CalendarProviderUnavailableError, which
    # also wraps a raw underlying provider exception) — same reasoning as
    # above, generic message only.
    logger.warning("Unhandled calendar error: %s", exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Something went wrong with the calendar. Please try again.",
    )


class WorkingHoursDay(BaseModel):
    open: str
    close: str

    @field_validator("open", "close")
    @classmethod
    def _valid_time(cls, value: str) -> str:
        try:
            hour_str, minute_str = value.split(":")
            hour, minute = int(hour_str), int(minute_str)
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError
        except ValueError as exc:
            raise ValueError("Time must be HH:MM in 24-hour format") from exc
        return value

    @model_validator(mode="after")
    def _close_after_open(self) -> "WorkingHoursDay":
        # Found in Sprint 35's audit: nothing previously checked ordering, so
        # a business could save backwards hours (e.g. close before open),
        # silently producing an inverted availability filter for bookings.
        if self.close <= self.open:
            raise ValueError("close must be after open")
        return self


class UpdateCalendarSettingsRequest(BaseModel):
    timezone: str | None = None
    working_hours: dict[str, WorkingHoursDay | None] | None = None

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        validate_timezone(value)
        return value

    @field_validator("working_hours")
    @classmethod
    def _valid_days(cls, value: dict | None) -> dict | None:
        if value is None:
            return value
        unknown = set(value) - _DAY_KEYS
        if unknown:
            raise ValueError(f"Unknown day key(s): {sorted(unknown)}")
        return value


def _get_business(db: Session, business_id: uuid.UUID) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return business


def _redirect_to_frontend(status_value: str, message: str | None = None) -> RedirectResponse:
    params = {"calendar": status_value}
    if message:
        params["message"] = message
    return RedirectResponse(url=f"{settings.frontend_url}/calendar?{urlencode(params)}")


@router.get("/settings")
def get_calendar_settings(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    business = _get_business(db, principal.business_id)
    return {"data": {"timezone": business.timezone, "working_hours": business.working_hours}}


@router.patch("/settings")
def update_calendar_settings(
    payload: UpdateCalendarSettingsRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")

    business = _get_business(db, principal.business_id)
    if "timezone" in updates:
        business.timezone = updates["timezone"]
    if "working_hours" in updates:
        business.working_hours = updates["working_hours"]
    db.commit()
    return {"data": {"timezone": business.timezone, "working_hours": business.working_hours}}


@router.get("/oauth/connect")
def start_oauth_connect(
    principal: Principal = Depends(get_current_principal),
) -> dict:
    try:
        authorization_url = oauth.build_authorization_url(principal.business_id)
    except CalendarError as exc:
        raise map_calendar_error(exc) from exc
    return {"data": {"authorization_url": authorization_url}}


@router.get("/oauth/callback", include_in_schema=False)
def oauth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Google redirects the user's browser here directly after consent — no
    Clerk session is possible. The signed `state` param authenticates this
    request instead, recovering which business initiated the connect."""
    if error:
        return _redirect_to_frontend("error", error)
    if not code or not state:
        return _redirect_to_frontend("error", "Missing authorization code")

    try:
        business_id = oauth.verify_state(state)
    except OAuthStateError as exc:
        logger.warning("Calendar OAuth callback rejected: %s", exc)
        return _redirect_to_frontend("error", "Invalid or expired connection request")

    try:
        refresh_token = oauth.exchange_code_for_refresh_token(code)
        calendar_credentials.store_credentials(db, business_id, refresh_token)
    except CalendarError as exc:
        # exc's own message can wrap a raw underlying oauthlib/google-auth
        # exception (app/calendar/oauth.py) — logged here, but never put in
        # the redirect URL a customer's browser follows (Sprint 52B, Task 5).
        logger.warning("Calendar OAuth exchange failed for business %s: %s", business_id, exc)
        return _redirect_to_frontend("error", "Couldn't connect Google Calendar. Please try again.")

    return _redirect_to_frontend("connected")


@router.get("/status")
def get_calendar_status(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    stored = calendar_credentials.get_stored_credential(db, principal.business_id)
    return {
        "data": {
            "connected": stored is not None,
            "calendar_id": stored.calendar_id if stored else None,
        }
    }


@router.delete("/disconnect", status_code=status.HTTP_204_NO_CONTENT)
def disconnect_calendar(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    calendar_credentials.disconnect(db, principal.business_id)


@router.get("/availability")
def get_availability(
    starts_at: datetime = Query(...),
    ends_at: datetime = Query(...),
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> dict:
    if ends_at <= starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be after starts_at")

    try:
        appointment_service = get_appointment_service(db, principal.business_id)
        slots = appointment_service.list_availability(starts_at=starts_at, ends_at=ends_at)
    except CalendarError as exc:
        raise map_calendar_error(exc) from exc

    return {
        "data": [
            {"starts_at": to_iso_utc(s.starts_at), "ends_at": to_iso_utc(s.ends_at)} for s in slots
        ]
    }
