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

Current state (Sprint 64A PR 6): `resolve()`, `validate_capability()`, and
`send()` are real — `send()` is now the production outbound entry point
for WhatsApp (via `app.services.messaging.send_via_channel_manager`, which
`app/ai/processing.py`/`app/services/replies.py`/`app/api/dashboard.py`
all call as their `sender`). `handle_inbound()` remains an
`NotImplementedError` stub — inbound routing through ChannelManager is a
later PR; PR 5 already cut inbound parsing over directly to
`app.channels.whatsapp.parsing`, which didn't need ChannelManager to do
that.

Nothing here does persistence, approvals, or CRM/AI work — see the
"Must never know about" paragraph above, unchanged by this PR.
"""

from __future__ import annotations

import logging
import time

from app.channels.base.capabilities import Capability
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import CapabilityNotSupportedError
from app.channels.base.message import NormalizedMessage, OutboundMessage
from app.channels.base.provider import ChannelProvider
from app.channels.base.results import DeliveryReceipt
from app.channels.registry import ChannelRegistry, get_default_registry

logger = logging.getLogger(__name__)

# Matches app/services/messaging.py::send_text's historical retry
# semantics exactly (3 attempts total, 0.2 * attempt-number backoff
# between tries) — see this module's send() docstring. Not the same
# Python constant as send_text's own `max_attempts=3` default (that
# function is retained, independently tested, and unchanged by this PR —
# see its module docstring) but deliberately the same *value*, so a
# WhatsApp send retries exactly as many times whichever path calls it.
DEFAULT_MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.2


class ChannelManager:
    def __init__(
        self,
        registry: ChannelRegistry | None = None,
        *,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._registry = registry if registry is not None else get_default_registry()
        self._max_attempts = max_attempts

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
        """Resolve `message.channel`'s provider, verify it supports TEXT
        (every outbound message today is plain text — no channel-name
        conditional, just a capability check that will do the right thing
        automatically once a caller ever constructs a media message), then
        call `provider.send()` up to `self._max_attempts` times.

        Retry conditions, count, and backoff are unchanged from
        `send_text`'s historical behavior, now expressed generically: a
        `DeliveryReceipt(status="failed", retryable=True)` (the provider's
        normalized equivalent of a 5xx/network failure) is retried with
        `RETRY_BACKOFF_SECONDS * attempt` sleeps between tries;
        `retryable=False` (a 4xx/malformed-response equivalent) returns
        immediately, exhausting no further attempts. `provider.send()`
        raising outright (a bug, not an ordinary delivery failure — see
        `ChannelProvider.send()`'s own contract) is caught here and turned
        into one final non-retryable failed receipt, the same "unexpected
        -> stop, don't retry blindly" treatment `send_text`'s own safety
        net gives an unanticipated exception.

        Raises `ProviderNotFoundError`/`CapabilityNotSupportedError` for a
        channel that isn't registered or can't take this message at all —
        a configuration problem, not an ordinary delivery failure, so
        these are exceptions rather than a returned failed receipt.
        """
        provider = self.resolve(message.channel)
        if not provider.capabilities().supports(Capability.TEXT):
            raise CapabilityNotSupportedError(
                f"Channel '{message.channel}' does not support 'text'"
            )

        last_receipt: DeliveryReceipt | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                receipt = provider.send(message, creds)
            except Exception as exc:  # noqa: BLE001 — see docstring: normalize, don't propagate
                logger.warning(
                    "Unexpected error from %s provider's send(): %s", message.channel, exc
                )
                return DeliveryReceipt(
                    status="failed", retryable=False, error=f"Unexpected provider error: {exc!r}"
                )

            if receipt.status == "sent" or not receipt.retryable:
                return receipt
            last_receipt = receipt
            if attempt < self._max_attempts:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        assert last_receipt is not None  # loop always runs >= 1 iteration
        return last_receipt

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
