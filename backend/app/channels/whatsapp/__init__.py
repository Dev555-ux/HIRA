"""WhatsApp's ChannelProvider implementation (Sprint 64A PR 3).

Deliberately does NOT register `WhatsAppProvider` into
`app.channels.registry.get_default_registry()` here. Auto-registering on
import would make this package's mere presence in an import graph change
what the registry reports — safer for that registration to be an explicit
line in whichever later PR actually wires a caller to it, so import-time
side effects stay at zero for this PR, matching its "nothing in production
uses this yet" scope.
"""

from __future__ import annotations

from app.channels.whatsapp.provider import WhatsAppProvider

__all__ = ["WhatsAppProvider"]
