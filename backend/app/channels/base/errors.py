"""Error hierarchy for the channel abstraction, mirroring the shape of
app/calendar/providers/base.py's CalendarError hierarchy and
app/whatsapp/errors.py — same convention, generalized across channels
instead of scoped to one integration.

Kept deliberately generic: nothing here mentions WhatsApp, Instagram, or
any other channel by name. A provider raises these for failures a caller
needs to branch on; anything a provider-specific caller doesn't need to
distinguish should just be a plain `ChannelError`.
"""

from __future__ import annotations


class ChannelError(RuntimeError):
    """Base error for the entire channel abstraction. Callers that only
    care "did something go wrong with messaging" can catch this alone."""


class ProviderNotFoundError(ChannelError):
    """Raised by the registry when asked to resolve a channel id nothing
    has registered a provider for."""


class CapabilityNotSupportedError(ChannelError):
    """Raised when a caller asks a provider to do something its
    `CapabilitySet` says it can't — e.g. sending a template message to a
    channel that doesn't support templates."""


class InvalidCredentialsError(ChannelError):
    """A provider's `validate_credentials()` call to the external API
    rejected the credential outright (bad token, revoked access, wrong
    account)."""


class WebhookVerificationFailedError(ChannelError):
    """A provider's `verify_webhook_signature()` returned False, or the
    request otherwise can't be trusted as genuinely from the platform."""


class DeliveryFailedError(ChannelError):
    """A provider's `send()` call to the external API failed. Carries
    enough of the underlying failure for ChannelManager's retry policy to
    decide whether it's worth retrying — see channel_manager.py."""


class ConnectionFailedError(ChannelError):
    """A provider's connection lifecycle (validate/connect) failed for a
    reason other than an invalid credential — e.g. the external API was
    unreachable."""
