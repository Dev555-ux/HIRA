"""HIRA backend entry point.

This creates the FastAPI application and exposes a single /health endpoint.
Everything else (webhooks, AI engine, calendar, etc.) will be added on top of
this skeleton in later Sprint 1 tasks.
"""

from fastapi import FastAPI

from app.webhooks.whatsapp import router as whatsapp_router

app = FastAPI(title="HIRA Backend", version="0.1.0")
app.include_router(whatsapp_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check — confirms the server is running.

    Used locally during development and later by monitoring/hosting to verify
    the service is up. Returns HTTP 200 with a small JSON body.
    """
    return {"status": "ok"}
