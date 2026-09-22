"""Embedded Signup provider factory.

`get_embedded_signup_provider()` returns the real Meta-backed provider on a
deployment whose Tech Provider configuration is complete, and the stub
otherwise (Sprint 83). The choice is made from configuration rather than a
separate flag: a deployment holding an app id, an app secret and a Business
Login configuration id can run the flow, and one missing any of them cannot,
so there is nothing further to decide. `ENABLE_EMBEDDED_SIGNUP` still gates
whether the routes exist at all (app/api/embedded_signup.py) — that's the
kill switch; this is the capability check.

The stub remains registered, not deleted: it's what an unconfigured
deployment (local dev, a staging box, production before the Meta variables
are set) gets, and it refuses honestly instead of failing halfway through a
real flow with a confusing Meta error.
"""

from __future__ import annotations

from app import meta
from app.whatsapp.providers.base import (
    EmbeddedSignupError,
    EmbeddedSignupNotConfiguredError,
    EmbeddedSignupProvider,
    EmbeddedSignupResult,
    EmbeddedSignupSession,
)
from app.whatsapp.providers.embedded_signup_meta import MetaEmbeddedSignupProvider
from app.whatsapp.providers.embedded_signup_stub import StubEmbeddedSignupProvider


def get_embedded_signup_provider() -> EmbeddedSignupProvider:
    if meta.tech_provider_configured():
        return MetaEmbeddedSignupProvider()
    return StubEmbeddedSignupProvider()


__all__ = [
    "EmbeddedSignupError",
    "EmbeddedSignupNotConfiguredError",
    "EmbeddedSignupProvider",
    "EmbeddedSignupResult",
    "EmbeddedSignupSession",
    "MetaEmbeddedSignupProvider",
    "StubEmbeddedSignupProvider",
    "get_embedded_signup_provider",
]
