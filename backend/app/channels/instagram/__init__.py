"""Instagram's ChannelProvider implementation (Sprint 65 PR 1 — foundation
only).

Registers `InstagramProvider` into the default channel registry on import
— same pattern as `app.channels.whatsapp` (see that package's
`__init__.py`). Unlike WhatsApp's, nothing in production imports this
package yet: there is no `app/webhooks/instagram.py`, and no
`MessagingService`/API code references `"instagram"` anywhere. Importing
this module (e.g. from a test) registers the provider into the shared
registry with no other effect — `get_default_registry().get("instagram")`
resolves to a real (if mostly unimplemented) provider, but nothing calls
it, and `ChannelManager.send()` would immediately raise
`CapabilityNotSupportedError` for it regardless (see
`provider.py::capabilities()`).
"""

from __future__ import annotations

from app.channels.instagram.provider import InstagramProvider
from app.channels.registry import get_default_registry

get_default_registry().register(InstagramProvider())

__all__ = ["InstagramProvider"]
