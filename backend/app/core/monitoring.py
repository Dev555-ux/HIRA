"""Error monitoring (Sentry) — Sprint 52B, Task 3.

Enabled only when SENTRY_DSN is set (Railway's Variables tab in production;
never set in local dev, so this is a no-op there by default — matches the
same "empty by default, real value only in Railway" convention every other
API key in app/core/config.py already follows).

sentry_sdk's own public API (capture_exception, set_tag, ...) is a
documented no-op when sentry_sdk.init() was never called, so every call site
elsewhere in the app (app/auth/dependencies.py, app/core/request_logging.py)
can call these functions unconditionally — no "is this configured" branch
needed outside this module.
"""

from __future__ import annotations

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.core.config import settings

# Stripped from any event before it leaves the process — defense-in-depth on
# top of send_default_pii=False below, not a replacement for it (Task 3:
# "Do not log API keys, JWTs, or customer message contents").
_SENSITIVE_HEADERS = {"authorization", "cookie", "x-hub-signature-256"}


def _scrub_event(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    request = event.get("request")
    if request and isinstance(request.get("headers"), dict):
        request["headers"] = {
            k: v for k, v in request["headers"].items() if k.lower() not in _SENSITIVE_HEADERS
        }
    return event


def init_sentry() -> None:
    """Call once at startup (app/main.py). No-ops if SENTRY_DSN is unset."""
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        # send_default_pii=False: business/user identity is attached
        # explicitly via set_business_context() below (a business_id tag),
        # not by letting the SDK capture request bodies/cookies/IPs
        # wholesale — those can carry a customer's own message text.
        send_default_pii=False,
        before_send=_scrub_event,
        # Error monitoring, not APM — no performance tracing, so this stays
        # exactly the one thing Task 3 asked for.
        traces_sample_rate=0.0,
    )


def set_business_context(business_id: str) -> None:
    sentry_sdk.set_tag("business_id", business_id)


def set_request_id_context(request_id: str) -> None:
    sentry_sdk.set_tag("request_id", request_id)


def capture_exception(exc: BaseException) -> None:
    """Explicit capture from app/main.py's own generic exception handler.

    Sentry's Starlette/FastAPI integration captures unhandled exceptions
    automatically, but this app already has its own catch-all handler
    (app/main.py::unhandled_exception_handler) that converts every unhandled
    exception into a generic 500 response — calling this there guarantees
    the exception reaches Sentry regardless of integration-level nuance
    around apps with their own exception handlers.
    """
    sentry_sdk.capture_exception(exc)
