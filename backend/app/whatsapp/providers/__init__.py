"""Embedded Signup provider factory.

`get_embedded_signup_provider()` returns the configured provider. Only the
stub is registered today (embedded_signup_stub.py) — a real Meta-backed
provider is added by implementing `EmbeddedSignupProvider` and swapping it in
here once Meta Tech Provider approval exists (TODOS.md ONBOARD-E); no caller
of this function needs to change.
"""

from __future__ import annotations

from app.whatsapp.providers.base import (
    EmbeddedSignupError,
    EmbeddedSignupNotConfiguredError,
    EmbeddedSignupProvider,
    EmbeddedSignupResult,
    EmbeddedSignupSession,
)
from app.whatsapp.providers.embedded_signup_stub import StubEmbeddedSignupProvider


def get_embedded_signup_provider() -> EmbeddedSignupProvider:
    return StubEmbeddedSignupProvider()


__all__ = [
    "EmbeddedSignupError",
    "EmbeddedSignupNotConfiguredError",
    "EmbeddedSignupProvider",
    "EmbeddedSignupResult",
    "EmbeddedSignupSession",
    "get_embedded_signup_provider",
]
