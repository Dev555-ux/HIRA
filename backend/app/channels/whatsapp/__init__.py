"""WhatsApp's ChannelProvider implementation.

Registers `WhatsAppProvider` into the default channel registry on import
(Sprint 64A PR 5) — the "explicit line in whichever later PR actually
wires a caller to it" this package's PR 3 docstring predicted. As of PR 7,
this registration is genuinely load-bearing: `webhooks/whatsapp.py::receive()`
resolves the provider via `ChannelManager().resolve("whatsapp")` (which
delegates to this registry) before calling `parse_webhook()`, and
`MessagingService._send()` resolves it the same way (via `ChannelManager.
send()`) before calling `send()`. See docs/architecture/messaging-platform.md
for the full picture.
"""

from __future__ import annotations

from app.channels.registry import get_default_registry
from app.channels.whatsapp.provider import WhatsAppProvider

get_default_registry().register(WhatsAppProvider())

__all__ = ["WhatsAppProvider"]
