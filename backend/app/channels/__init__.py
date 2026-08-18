"""Multi-channel messaging foundation.

Everything under this package is the channel abstraction: DTOs, the
`ChannelProvider` interface, the registry, and one subpackage per channel
(`app.channels.whatsapp`, `app.channels.instagram`, ...). See
documentation/architecture/messaging-platform.md for the full picture.

`register_all()` below exists to fix a real production bug (found while
building Sprint 65 PR 1): a channel package registers itself into the
default registry as an import-time side effect (see e.g.
`app.channels.whatsapp`'s own `__init__.py` docstring) — but nothing in
`app.main`'s actual import graph was guaranteed to import that package.
Sprint 64A PR 7 removed `webhooks/whatsapp.py`'s direct
`from app.channels.whatsapp.parsing import ...` import (replacing it with
`ChannelManager().resolve("whatsapp")`), which had been the only thing
triggering registration in production — nothing replaced it. In a real
deploy (`uvicorn app.main:app`, no test suite involved), the default
registry started genuinely empty, so the first inbound webhook raised
`ProviderNotFoundError` instead of resolving `WhatsAppProvider`. Every
test still passed, because pytest's collection phase imports test modules
that import `app.channels.whatsapp` directly, silently registering it for
the rest of that process before any `TestClient` request runs — a gap
invisible to the suite and only visible in a genuinely fresh process.

`register_all()` makes registration an explicit, visible step instead of
an accidental one — call it once, at application startup
(`app/main.py`), before anything might resolve a provider.
"""

from __future__ import annotations


def register_all() -> None:
    """Import every channel package that should be registered in this
    deployment. Each import is the trigger for that package's own
    `get_default_registry().register(...)` call — see e.g.
    `app.channels.whatsapp.__init__`. Registering a provider here does
    NOT route any production traffic to it by itself (see
    `documentation/architecture/messaging-platform.md` — routing requires
    a webhook route and/or a MessagingService credential-resolution path
    that actually calls `ChannelManager.resolve(channel_id)`); it only
    guarantees `get_default_registry().get(channel_id)` can find the
    provider when something legitimately does.
    """
    import app.channels.whatsapp  # noqa: F401
