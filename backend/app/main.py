"""HIRA backend entry point.

This creates the FastAPI application and exposes a single /health endpoint.
Everything else (webhooks, AI engine, calendar, etc.) will be added on top of
this skeleton in later Sprint 1 tasks.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


from app.api.appointments import router as appointments_router
from app.api.calendar import router as calendar_router
from app.api.conversations import router as conversations_router
from app.api.customers import router as customers_router
from app.api.dashboard import router as dashboard_router
from app.api.knowledge_base import router as knowledge_base_router
from app.api.leads import router as leads_router
from app.api.onboarding import router as onboarding_router
from app.api.settings import router as settings_router
from app.core.config import settings
from app.webhooks.whatsapp import router as whatsapp_router

logger = logging.getLogger(__name__)

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
    """
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Fixed localhost dev ports, the production Vercel domain, plus
# settings.frontend_url so a deployed frontend isn't CORS-blocked once
# FRONTEND_URL is set to the real domain (Sprint 34). allow_origins only
# does exact string matches, so Vercel preview deployments (random
# *.vercel.app subdomains per branch/PR) can never be listed individually —
# they're matched separately via allow_origin_regex below. Without that
# regex, Starlette's CORSMiddleware rejects any non-matching Origin on the
# preflight with a 400 "Disallowed CORS origin", which is what was breaking
# every OPTIONS request from Vercel.
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
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(whatsapp_router)
app.include_router(dashboard_router)
app.include_router(knowledge_base_router)
app.include_router(onboarding_router)
app.include_router(settings_router)
app.include_router(conversations_router)
app.include_router(leads_router)
app.include_router(customers_router)
app.include_router(calendar_router)
app.include_router(appointments_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check — confirms the server is running.

    Used locally during development and later by monitoring/hosting to verify
    the service is up. Returns HTTP 200 with a small JSON body.
    """
    return {"status": "ok"}
