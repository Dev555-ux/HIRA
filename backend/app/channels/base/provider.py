"""The ChannelProvider interface — the contract every messaging channel
(WhatsApp, Instagram, Messenger, Email, Website Chat, ...) implements.

Purpose: let `ChannelManager` (app/services/channel_manager.py) and,
eventually, `MessagingService` (app/services/messaging_service.py) call any
channel identically. `ChannelManager` depends only on this interface, never
on a concrete provider — a new channel is added by implementing this class
and registering it (app/channels/registry/), with no change to anything
that already works. Modeled after app/calendar/providers/base.py's
CalendarProvider shape, generalized to messaging.

Responsibilities a provider MUST fulfil: translate its native webhook
payload into `NormalizedMessage`; translate an `OutboundMessage` into a
native API call; verify that an inbound webhook request genuinely came
from the platform; report a stable `channel_id` and `CapabilitySet`;
validate a credential against the live external API.

What a provider MUST NOT do — enforced by convention here (every method
signature below takes only DTOs, never a session or ORM type):

- receive a SQLAlchemy `Session`
- import or reference any ORM model (`Business`, `Customer`,
  `Conversation`, `Message`, ...)
- query or write to the database
- perform persistence of any kind
- update CRM state (leads, customers)
- invoke the AI layer

A provider is a pure transport adapter: native payload in, DTO out; DTO
in, native API call out. Everything stateful — who a message is from,
whether to actually send a reply, what to log — belongs to
`MessagingService`/`ChannelManager`, which are the only layers in this
pipeline allowed to touch a database.

This module intentionally contains no implementation — `ChannelProvider` is
an ABC with abstract methods only. The first concrete implementation
(`WhatsAppProvider`, wrapping today's app/webhooks/whatsapp.py and
app/services/messaging.py logic) is a later PR in the Sprint 64A sequence,
not this one. Nothing in this PR is registered, imported by, or reachable
from any production code path.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Mapping

from app.channels.base.capabilities import CapabilitySet
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.message import NormalizedMessage, OutboundMessage
from app.channels.base.results import ConnectionResult, DeliveryReceipt


class ChannelProvider(ABC):
    """Base class for a single messaging channel's transport adapter.

    `channel_id` is the stable string every other layer (Registry,
    ChannelManager, the eventual `Conversation.channel` column) uses to
    refer to this channel — e.g. "whatsapp", "instagram". It must be a
    class attribute set by the subclass, not derived at runtime, so the
    Registry can register a provider by id without instantiating it first
    if it chooses to.
    """

    channel_id: str

    @abstractmethod
    def capabilities(self) -> CapabilitySet:
        """What this channel supports. Static per provider — does not vary
        per business or per message. Callers use this to decide whether an
        operation is even worth attempting, not to decide *how* to attempt
        it."""

    @abstractmethod
    def validate_credentials(self, creds: ChannelCredentials) -> ConnectionResult:
        """Make a live call to the external API to confirm `creds` actually
        works. Used during the connect/onboarding flow — never called on
        the per-message hot path. Must not raise for an ordinary
        credential failure (wrong token, revoked access); report that via
        `ConnectionResult(success=False, error=...)` instead. Reserve
        raising `ConnectionFailedError` for the external API itself being
        unreachable."""

    @abstractmethod
    def extract_routing_key(self, raw_body: bytes) -> str:
        """An unauthenticated peek at a raw webhook body to find whatever
        id tells the caller *which business* this request is for (e.g.
        WhatsApp's `phone_number_id`). Must not trust the body's contents
        for anything beyond this lookup — the caller (ChannelManager) uses
        the returned key to load that business's `ChannelCredentials`
        *before* calling `verify_webhook_signature()`, since verifying a
        signature requires already knowing whose secret to check it
        against."""

    @abstractmethod
    def verify_webhook_signature(
        self, headers: Mapping[str, str], raw_body: bytes, creds: ChannelCredentials
    ) -> bool:
        """True only if `raw_body` is authentically signed by the
        platform, per that channel's own signing scheme (e.g. WhatsApp's
        `X-Hub-Signature-256` HMAC). Never raises for a bad signature —
        returns False; the caller decides what a False means (reject the
        request)."""

    @abstractmethod
    def verify_subscription(
        self, query_params: Mapping[str, str], creds: ChannelCredentials
    ) -> str | None:
        """Handle a platform's GET-time webhook-subscription handshake
        (e.g. Meta's `hub.challenge`). Returns the value the platform
        expects echoed back, or None if this request isn't a valid
        handshake for this channel."""

    @abstractmethod
    def parse_webhook(self, raw_body: bytes) -> list[NormalizedMessage]:
        """Translate an already-signature-verified webhook body into zero
        or more `NormalizedMessage`. Returns an empty list for payload
        types this channel receives but doesn't represent as messages
        (e.g. delivery-status callbacks) — never raises for a payload
        shape the channel legitimately sends, only for something
        genuinely malformed."""

    @abstractmethod
    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
        """A single attempt to deliver `message` via the external API — no
        internal retry loop. Retry policy belongs to ChannelManager, not
        here, so failures compose predictably instead of two layers
        retrying independently. Must not raise for an ordinary delivery
        failure; report it via `DeliveryReceipt(status="failed", error=...)`
        instead. Reserve raising `DeliveryFailedError` for cases the caller
        genuinely cannot proceed past (e.g. malformed credentials)."""
