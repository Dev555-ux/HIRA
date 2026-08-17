"""Public surface of the channel abstraction's base contracts.

Callers (a future provider implementation, ChannelManager, the registry)
import from `app.channels.base` rather than reaching into the individual
submodules — same convention as app/whatsapp/providers/__init__.py.
"""

from __future__ import annotations

from app.channels.base.capabilities import Capability, CapabilitySet
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import (
    CapabilityNotSupportedError,
    ChannelError,
    ConnectionFailedError,
    DeliveryFailedError,
    InvalidCredentialsError,
    ProviderNotFoundError,
    WebhookVerificationFailedError,
)
from app.channels.base.message import MediaKind, MediaRef, NormalizedMessage, OutboundMessage
from app.channels.base.provider import ChannelProvider
from app.channels.base.results import ConnectionResult, DeliveryReceipt

__all__ = [
    "Capability",
    "CapabilityNotSupportedError",
    "CapabilitySet",
    "ChannelCredentials",
    "ChannelError",
    "ChannelProvider",
    "ConnectionFailedError",
    "ConnectionResult",
    "DeliveryFailedError",
    "DeliveryReceipt",
    "InvalidCredentialsError",
    "MediaKind",
    "MediaRef",
    "NormalizedMessage",
    "OutboundMessage",
    "ProviderNotFoundError",
    "WebhookVerificationFailedError",
]
