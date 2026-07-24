"""HIRA backend entry point.

This creates the FastAPI application and exposes a single /health endpoint.
Everything else (webhooks, AI engine, calendar, etc.) will be added on top of
this skeleton in later Sprint 1 tasks.
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session


from app.api.appointments import router as appointments_router
from app.api.calendar import router as calendar_router
from app.api.conversations import router as conversations_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.escalations import router as escalations_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.leads import router as leads_router
from app.api.onboarding import router as onboarding_router
from app.api.settings import router as settings_router
from app.api.whatsapp import router as whatsapp_api_router
from app.core.config import settings
from app.core.monitoring import capture_exception, capture_message, init_sentry
from app.core.rate_limit import init_rate_limiting
from app.core.request_logging import RequestLoggingMiddleware
from app.db.session import get_db
from app.models import Message
from app.webhooks.whatsapp import router as whatsapp_router

logger = logging.getLogger(__name__)


def _configure_app_logging() -> None:
    """Make every app.*'s logger.info()/.warning()/.exception() call actually
    emit, in local dev and production alike (Section A5).

    Python's root logger defaults to level WARNING with no handler attached,
    so every `logging.getLogger(__name__)` in this codebase was silently
    dropping INFO records — only WARNING/ERROR ever appeared, via Python's
    last-resort stderr fallback, not any configuration this app owns.

    This attaches one handler directly to the "app" logger — the shared
    ancestor of every app.* module logger — and stops it there
    (propagate=False), the same pattern uvicorn's own default logging
    config uses for its "uvicorn"/"uvicorn.access" loggers. That keeps this
    fully independent of uvicorn's own loggers and of the root logger: it
    can't create duplicate lines (each record is handled exactly once, by
    this handler), and it works no matter whether uvicorn has configured
    its own logging yet or not, since nothing here touches uvicorn's
    loggers or root. Guarded by `if app_logger.handlers` so re-importing
    this module in the same process (e.g. across test files) can't attach
    a second handler and double every line.
    """
    app_logger = logging.getLogger("app")
    if app_logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False


_configure_app_logging()
init_sentry()

app = FastAPI(title="HIRA Backend", version="0.1.0")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for anything no route/dependency explicitly handled.

    FastAPI registers its own handlers for HTTPException and
    RequestValidationError, which the ASGI exception middleware matches
    before falling back to this one (it looks up the closest registered
    class in the exception's MRO) — so normal 401/404/409/422/502/503
    responses are unaffected. This only fires for genuine bugs, which
    previously surfaced as a bare 500 with zero application-level log entry
    (Starlette's default handler doesn't log anything; only uvicorn's raw
    stderr traceback, unstructured and with no request context).

    Response body is deliberately generic (Sprint 52B, Task 5) — a stack
    trace or exception name/message here would be shown directly to the
    customer; the real detail stays server-side, in this log line and in
    Sentry (capture_exception — a no-op unless SENTRY_DSN is set).
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    capture_exception(exc)
    return JSONResponse(
        status_code=500, content={"detail": "Something went wrong. Please try again."}
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """FastAPI's default handler for this exception returns `detail` as a
    *list* of Pydantic error dicts (type/loc/msg/...) — every manually raised
    HTTPException elsewhere in this app returns `detail` as a plain string,
    and the frontend's error rendering (frontend/src/lib/api.ts's ApiError)
    assumes exactly that (Sprint 52B, Task 5/2 regression: adding a
    `max_length` to a field made its 422 render as the literal text
    "[object Object]" in the UI — a list of objects coerced to a string).

    Same "field: message" join style app/core/config.py's own
    _load_settings() already uses for its own Pydantic errors, minus the
    "body"/"query" location prefix, which isn't meaningful to a customer.
    """
    detail = "; ".join(
        f"{'.'.join(str(p) for p in err['loc'][1:]) or 'value'}: {err['msg']}"
        for err in exc.errors()
    )
    return JSONResponse(status_code=422, content={"detail": detail})


# Fixed localhost dev ports, the production Vercel domain, plus
# settings.frontend_url so a deployed frontend isn't CORS-blocked once
# FRONTEND_URL is set to the real domain (Sprint 34). allow_origins only
# does exact string matches, so Vercel preview deployments (random
# hira-<branch/hash>-<team>.vercel.app subdomains per branch/PR) can never
# be listed individually — they're matched separately via allow_origin_regex
# below. Without that regex, Starlette's CORSMiddleware rejects any
# non-matching Origin on the preflight with a 400 "Disallowed CORS origin",
# which is what was breaking every OPTIONS request from Vercel.
#
# A11 (Sprint S1 security audit): this regex previously matched
# `https://.*\.vercel\.app` — *any* site hosted on Vercel, not just this
# project's own deployments, since Vercel is a shared multi-tenant host
# anyone can deploy to. Narrowed to require the subdomain start with
# "hira-", matching this project's actual preview-deployment naming
# (Vercel names previews after the project, "hira"). This isn't a perfect
# allowlist — nothing stops a third party from naming their own Vercel
# project "hira-something" — but it closes the "literally anyone on
# vercel.app" gap the audit flagged. Tighten further to this project's
# exact Vercel team/project slug once a real deployment fixes what that is.
_CORS_ORIGINS = {
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "https://hira-tau.vercel.app",
    settings.frontend_url,
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_CORS_ORIGINS),
    allow_origin_regex=r"https://hira-[a-zA-Z0-9-]*\.vercel\.app",
    # A11: no cookie-based credential is ever sent cross-origin — the
    # frontend authenticates via an explicit `Authorization: Bearer` header
    # (frontend/src/lib/api.ts), never `credentials: "include"` — so this
    # was doing nothing but widening the policy for no functional benefit.
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added after CORSMiddleware so it's the outermost middleware (Starlette
# wraps in reverse add order) — the per-request log line then covers the
# full round trip, CORS handling included (Sprint 52B, Task 4).
app.add_middleware(RequestLoggingMiddleware)
init_rate_limiting(app)
app.include_router(whatsapp_router)
app.include_router(whatsapp_api_router)
app.include_router(dashboard_router)
app.include_router(knowledge_base_router)
app.include_router(onboarding_router)
app.include_router(settings_router)
app.include_router(conversations_router)
app.include_router(leads_router)
app.include_router(customers_router)
app.include_router(calendar_router)
app.include_router(appointments_router)
app.include_router(escalations_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check — confirms the server is running.

    Used locally during development and later by monitoring/hosting to verify
    the service is up. Returns HTTP 200 with a small JSON body.
    """
    return {"status": "ok"}


@app.get("/health/whatsapp")
def health_whatsapp(db: Session = Depends(get_db)) -> JSONResponse:
    """Webhook liveness signal (Sprint 69, DEPLOY-5) — not "is the server
    up" (that's /health above), but "have we actually heard from Meta
    recently." Deliberately separate from /health: Railway's own
    healthcheckPath (railway.json) stays pointed at /health so a quiet
    webhook (e.g. a pilot business with no messages overnight) never causes
    a restart loop — this endpoint is meant to be polled by an external
    uptime monitor (see documentation/DEPLOYMENT.md), not Railway itself.

    Datetimes here are naive/UTC-implied, matching every other timestamp
    column in this app (see DEC-032's note on Appointment timestamps) — no
    tz-aware comparison is needed or attempted.
    """
    latest = db.scalars(
        select(Message.created_at)
        .where(Message.direction == "inbound")
        .order_by(Message.created_at.desc())
        .limit(1)
    ).first()
    if latest is None:
        return JSONResponse(status_code=200, content={"status": "no_traffic_yet"})

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    age = now - latest
    threshold = timedelta(minutes=settings.webhook_stale_threshold_minutes)
    if age > threshold:
        capture_message(
            f"WhatsApp webhook silent for {age}, exceeding the "
            f"{threshold} threshold (last inbound message at {latest.isoformat()})."
        )
        return JSONResponse(
            status_code=503,
            content={"status": "stale", "last_inbound_at": latest.isoformat()},
        )
    return JSONResponse(
        status_code=200, content={"status": "ok", "last_inbound_at": latest.isoformat()}
    )
