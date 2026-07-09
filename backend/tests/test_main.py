"""Tests for app/main.py: CORS configuration (Sprint 34).

settings.frontend_url must be in the allowed origins — otherwise a deployed
frontend (FRONTEND_URL set to the real domain) would be CORS-blocked from
calling this API at all, even with a valid Clerk token."""

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


def test_frontend_url_is_an_allowed_cors_origin():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": settings.frontend_url})

    assert response.headers.get("access-control-allow-origin") == settings.frontend_url


def test_dev_localhost_origins_remain_allowed():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "http://localhost:3000"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_an_unrecognized_origin_is_not_allowed():
    client = TestClient(app)

    response = client.get("/health", headers={"Origin": "https://evil.example.com"})

    assert "access-control-allow-origin" not in response.headers
