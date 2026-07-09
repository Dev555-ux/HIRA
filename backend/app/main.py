"""HIRA backend entry point.

This creates the FastAPI application and exposes a single /health endpoint.
Everything else (webhooks, AI engine, calendar, etc.) will be added on top of
this skeleton in later Sprint 1 tasks.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

app = FastAPI(title="HIRA Backend", version="0.1.0")

# Fixed localhost dev ports, plus settings.frontend_url so a deployed
# frontend isn't CORS-blocked once FRONTEND_URL is set to the real domain
# (Sprint 34) — previously hardcoded to only the three dev ports below, with
# no path from FRONTEND_URL into this list despite config.py's own comment
# claiming they were kept in sync.
_CORS_ORIGINS = {
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    settings.frontend_url,
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(_CORS_ORIGINS),
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
