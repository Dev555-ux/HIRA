"""API rate limiting (Sprint 52B, Task 1).

In-memory storage (slowapi/limits' default) — this is a single-instance
deployment (see ONBOARDING_ARCHITECTURE.md's reasoning against adding infra
ahead of real need), so a shared store (Redis) would be pure overhead for a
5-10 person beta; revisit if/when this ever runs more than one instance.

Limits are configurable via environment variables (app/core/config.py),
never hardcoded — each protected route reads `settings.rate_limit_*` through
a lambda, so the value is re-read per-request rather than frozen at import
time (this is also what makes it possible for tests to monkeypatch a limit
and see it take effect immediately).

Business-scoped where an authenticated principal exists (the key_func below
reads `request.state.business_id`, set by
app/auth/dependencies.py::get_current_principal); IP-scoped otherwise (e.g.
business creation, which by definition happens before any business exists).
"""

from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def _rate_limit_key(request: Request) -> str:
    business_id = getattr(request.state, "business_id", None)
    if business_id:
        return f"business:{business_id}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)


def _retry_after_seconds(request: Request) -> int:
    """Mirrors slowapi's own _inject_headers computation (extension.py) —
    duplicated rather than reused because that method is gated behind
    `headers_enabled`, which must stay off here: turning it on makes
    slowapi's per-route decorator try to inject headers into the *successful*
    response too, and every route in this app returns a plain dict (not a
    Response), which that code path can't handle without every decorated
    endpoint also declaring an unused `response: Response` parameter."""
    try:
        view_rate_limit = request.state.view_rate_limit
        window_stats = limiter.limiter.get_window_stats(view_rate_limit[0], *view_rate_limit[1])
        return max(1, int(1 + window_stats[0] - time.time()))
    except Exception:
        return 60


def _handle_rate_limit_exceeded(request: Request, exc: RateLimitExceeded) -> Response:
    retry_after = _retry_after_seconds(request)
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please slow down and try again shortly."},
        headers={"Retry-After": str(retry_after)},
    )


def init_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _handle_rate_limit_exceeded)
