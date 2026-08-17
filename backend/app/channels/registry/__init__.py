"""Channel registry — resolves a channel id to a provider instance.

Purpose: the one place `ChannelManager` asks "who handles this channel?"
without knowing or caring which providers exist. Modeled after
app/calendar/providers/__init__.py's `_PROVIDERS` factory pattern, extended
with an explicit `register()` call instead of a hardcoded dict, since
future provider packages (channels/whatsapp/, channels/instagram/, ...)
each register themselves rather than this module importing every provider
by name.

Responsibilities: register a provider instance under its `channel_id`;
resolve a provider by channel id; list which channels are currently
registered.

Does NOT do: retries, logging, capability validation, credential loading,
configuration, or any API call. If a future change wants to add any of
those here, it belongs in ChannelManager instead — this class stays a
lookup table on purpose, so it's trivial to reason about and trivial to
test.

Why a class instead of a bare module-level dict (unlike the calendar
factory): `register()` mutates state, and a single shared module-level
dict would leak registrations between tests. `ChannelRegistry` instances
are cheap to construct fresh per test; `get_default_registry()` below
exists for the one shared instance production code will register real
providers into once they exist.

Nothing in this PR calls `register()` — it starts empty. The first caller
is the (not-yet-built) `WhatsAppProvider`'s package `__init__.py`, in a
later PR.
"""

from __future__ import annotations

from app.channels.base.errors import ProviderNotFoundError
from app.channels.base.provider import ChannelProvider


class ChannelRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, ChannelProvider] = {}

    def register(self, provider: ChannelProvider) -> None:
        """Registers `provider` under its own `channel_id`. Registering a
        second provider under the same `channel_id` replaces the first —
        callers that need to detect an accidental double-registration
        should check `is_registered()` first."""
        self._providers[provider.channel_id] = provider

    def is_registered(self, channel_id: str) -> bool:
        return channel_id in self._providers

    def get(self, channel_id: str) -> ChannelProvider:
        """Raises ProviderNotFoundError for an unregistered channel id —
        never returns None, so callers don't need a null check."""
        provider = self._providers.get(channel_id)
        if provider is None:
            raise ProviderNotFoundError(
                f"No provider registered for channel '{channel_id}'. "
                f"Registered: {sorted(self._providers) or 'none'}"
            )
        return provider

    def available(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))


_default_registry = ChannelRegistry()


def get_default_registry() -> ChannelRegistry:
    """The shared registry production code registers real providers into.
    Tests should construct their own `ChannelRegistry()` instead, to avoid
    cross-test state leakage."""
    return _default_registry


__all__ = ["ChannelRegistry", "get_default_registry"]
