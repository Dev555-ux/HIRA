"""WhatsApp's ChannelProvider implementation.

Registers `WhatsAppProvider` into the default channel registry on import
(Sprint 64A PR 5) — the "explicit line in whichever later PR actually
wires a caller to it" this package's PR 3 docstring predicted. This alone
does not route any live traffic through the registry: `webhooks/
whatsapp.py::_persist_inbound` calls `parsing.parse_messages()` directly
(it needs finer, per-`change` granularity than a registry lookup gives —
see that function's docstring), not `registry.get("whatsapp")`. This
registration exists so `get_default_registry().get("whatsapp")` resolves
to a real provider today, rather than the next PR that adds ChannelManager
routing also having to remember to register one.
"""

from __future__ import annotations

from app.channels.registry import get_default_registry
from app.channels.whatsapp.provider import WhatsAppProvider

get_default_registry().register(WhatsAppProvider())

__all__ = ["WhatsAppProvider"]
