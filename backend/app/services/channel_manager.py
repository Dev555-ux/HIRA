"""ChannelManager — the reliability layer between MessagingService and a
channel's Provider.

Purpose: everything about calling a channel *reliably* lives here, so
providers can stay dumb transport adapters and MessagingService doesn't
need to know a channel exists beyond its id.

Responsibilities (final, once fully built out):

- resolve a provider for a channel id (via the Registry)
- validate that an outbound message's requirements are within the
  provider's declared capabilities before ever calling it
- retry/backoff policy for transient send failures
- delivery tracking (turning a DeliveryReceipt into whatever
  MessagingService needs to update a Message row)
- structured logging and metrics per channel
- future: rate limiting, fallback routing between providers

Must never know about: the database, ORM models, `Business`/`Conversation`,
approvals, CRM, analytics. It receives `ChannelCredentials` as a parameter
— it never fetches credentials itself. If a method here starts needing a
`Session`, that logic has drifted into MessagingService's territory and
belongs there instead.

Current state (Sprint 64A PR 2 — foundation only): `resolve()` and
`validate_capability()` are real, because they're simple enough not to
need retry/logging/metrics infrastructure first and are needed to make the
class usable at all. `send()` and `handle_inbound()` are intentionally
`NotImplementedError` stubs — retry policy, logging, and metrics are
scoped to a later PR (Sprint 64A PR 5), and building them now, unused,
would be exactly the speculative complexity this PR is supposed to avoid.

Nothing in production constructs or calls `ChannelManager` yet.
"""

from __future__ import annotations

from app.channels.base.capabilities import Capability
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import CapabilityNotSupportedError
from app.channels.base.message import NormalizedMessage, OutboundMessage
from app.channels.base.provider import ChannelProvider
from app.channels.base.results import DeliveryReceipt
from app.channels.registry import ChannelRegistry, get_default_registry


class ChannelManager:
    def __init__(self, registry: ChannelRegistry | None = None) -> None:
        self._registry = registry if registry is not None else get_default_registry()

    def resolve(self, channel_id: str) -> ChannelProvider:
        """Raises ProviderNotFoundError (from the registry) if `channel_id`
        has no provider registered."""
        return self._registry.get(channel_id)

    def validate_capability(self, channel_id: str, capability: Capability) -> None:
        """Raises CapabilityNotSupportedError if the resolved provider
        doesn't declare `capability`. Callers that need the provider
        anyway should call `resolve()` separately — this method only
        validates, it doesn't return anything on success."""
        provider = self.resolve(channel_id)
        if not provider.capabilities().supports(capability):
            raise CapabilityNotSupportedError(
                f"Channel '{channel_id}' does not support '{capability.value}'"
            )

    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
        """Future: resolve the provider for `message.channel`, validate
        capabilities, apply retry/backoff on transient failures, log and
        record metrics, then call `ChannelProvider.send()`. Not
        implemented in this PR — see module docstring."""
        raise NotImplementedError(
            "ChannelManager.send() is scoped to Sprint 64A PR 5 (retry, logging, metrics). "
            "This PR only lands the resolve/validate skeleton."
        )

    def handle_inbound(
        self, channel_id: str, raw_body: bytes, headers: dict[str, str]
    ) -> list[NormalizedMessage]:
        """Future: resolve the provider, extract the routing key, load
        that business's credentials, verify the webhook signature, then
        call `ChannelProvider.parse_webhook()`. Not implemented in this
        PR — see module docstring."""
        raise NotImplementedError(
            "ChannelManager.handle_inbound() is scoped to a later PR in the Sprint 64A "
            "sequence. This PR only lands the resolve/validate skeleton."
        )
