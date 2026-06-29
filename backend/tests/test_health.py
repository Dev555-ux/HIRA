"""Tests for the /health endpoint.

Uses FastAPI's TestClient, which calls the app in-memory — no running server
needed. This is our first real behaviour test: it proves the endpoint returns
the expected status code and body.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
