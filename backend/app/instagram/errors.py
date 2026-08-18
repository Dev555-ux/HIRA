"""Instagram-domain exceptions (Sprint 65 PR 2) — mirrors
app/whatsapp/errors.py's shape. Distinct from app/channels/base/errors.py's
ChannelProvider-contract exceptions: these are about the connection/OAuth
flow (app/instagram/oauth.py, credentials.py), not about
ChannelProvider.send()/parse_webhook()."""

from __future__ import annotations


class InstagramError(Exception):
    """Base class for every Instagram-domain error."""


class InstagramNotConfiguredError(InstagramError):
    """This deployment hasn't set INSTAGRAM_APP_ID/INSTAGRAM_APP_SECRET/
    INSTAGRAM_OAUTH_REDIRECT_URI or CALENDAR_ENCRYPTION_KEY."""


class InstagramOAuthStateError(InstagramError):
    """The `state` param is missing, malformed, forged, expired, or reused."""


class InstagramAuthError(InstagramError):
    """A live Meta API call (token exchange, Page discovery, health check)
    failed."""


class InstagramDuplicateConnectionError(InstagramError):
    """This Instagram business account is already connected to a different
    business."""
