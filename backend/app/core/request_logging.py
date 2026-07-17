"""Per-request structured logging + request ID propagation (Sprint 52B, Task 4).

One log line per request, through the existing "app" logger (app/main.py's
_configure_app_logging already gives it a handler/formatter — this doesn't
introduce a second logging setup). The request ID is generated here (or
reused from an incoming X-Request-ID, so a request that already passed
through another hop keeps the same one), stashed on `request.state` for
anything downstream that wants it (error monitoring — see
app/core/monitoring.py), and echoed back in the response header so a user's
bug report can be tied to a specific log line.

business_id isn't known until deep inside dependency resolution
(app/auth/dependencies.py::get_current_principal is the first place that
knows it) — read from `request.state.business_id` only after the response
comes back, which is why this is a middleware wrapping the whole request
rather than something decided up front.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.monitoring import set_request_id_context

logger = logging.getLogger("app.request")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_id_context(request_id)  # no-op unless SENTRY_DSN is set

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            self._log(request, request_id, status_code=500, duration_ms=duration_ms)
            raise

        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        self._log(request, request_id, status_code=response.status_code, duration_ms=duration_ms)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    @staticmethod
    def _log(request: Request, request_id: str, *, status_code: int, duration_ms: float) -> None:
        # Never the querystring or body — only what's needed to correlate a
        # user's report with a log line, never content a customer typed.
        business_id = getattr(request.state, "business_id", None)
        logger.info(
            "request_id=%s method=%s path=%s status=%s duration_ms=%s business_id=%s",
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            business_id or "-",
        )
