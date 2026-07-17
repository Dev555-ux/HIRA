"""Tests for API rate limiting (Sprint 52B, Task 1).

Limits are set high in production defaults (app/core/config.py), so these
tests monkeypatch them down to something trivial to trigger deterministically
without sending dozens of requests.
"""

from fastapi.testclient import TestClient

from app.ai.llm.mock import MockProvider
from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, User
from tests.test_knowledge_base import FakeEmbeddingProvider


def _seed_business(db, name, clerk_user_id):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    user = User(business_id=biz.id, clerk_user_id=clerk_user_id, email=f"{name}@x.com")
    db.add(user)
    db.flush()
    return biz, user


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def _mock_providers(monkeypatch, *, fixed_reply="Mock reply"):
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply=fixed_reply),
    )
    monkeypatch.setattr(
        "app.ai.knowledge_base.get_embedding_provider", lambda name=None: FakeEmbeddingProvider()
    )


def test_demo_chat_rate_limit_returns_429_with_retry_after(db_session, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_demo_chat", "1/minute")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_providers(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    first = client.post(
        "/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "hi"}
    )
    second = client.post(
        "/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "hi again"}
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers
    assert int(second.headers["Retry-After"]) > 0
    # Matches this app's existing error-response convention (`detail`, not
    # slowapi's own default `error` key) — apiFetch() (frontend/src/lib/api.ts)
    # only ever reads `detail`.
    assert "detail" in second.json()
    assert second.json()["detail"]
    app.dependency_overrides.clear()


def test_demo_chat_rate_limit_is_scoped_per_business(db_session, monkeypatch):
    # A business hitting its own limit must not affect a different business.
    monkeypatch.setattr(settings, "rate_limit_demo_chat", "1/minute")
    _seed_business(db_session, "A", "user_a")
    _seed_business(db_session, "B", "user_b")
    db_session.commit()
    _mock_providers(monkeypatch)

    client_a = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    client_a.post("/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "hi"})
    limited = client_a.post(
        "/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "hi"}
    )
    assert limited.status_code == 429

    client_b = _client(db_session, claims_for_token=lambda t: {"sub": "user_b"})
    ok = client_b.post(
        "/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "hi"}
    )
    assert ok.status_code == 200
    app.dependency_overrides.clear()


def test_kb_upload_rate_limit_returns_429(db_session, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_kb_upload", "1/minute")
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    first = client.post("/api/v1/kb", headers=_auth(), json={"title": "Hours", "content": "9-5"})
    second = client.post(
        "/api/v1/kb", headers=_auth(), json={"title": "More hours", "content": "9-5 too"}
    )

    assert first.status_code == 201
    assert second.status_code == 429
    app.dependency_overrides.clear()


def test_business_creation_rate_limit_returns_429(db_session, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_business_creation", "1/hour")
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_new_1"})

    first = client.post(
        "/api/v1/onboarding/business",
        json={"name": "Acme", "owner_email": "a@acme.com"},
        headers=_auth(),
    )
    # A *different* Clerk identity but the same client (same IP, since this
    # route has no business yet to scope by) still hits the same IP-scoped
    # limit — this endpoint has no business_id to key on before one exists.
    second = client.post(
        "/api/v1/onboarding/business",
        json={"name": "Acme 2", "owner_email": "b@acme.com"},
        headers=_auth(),
    )

    assert first.status_code == 201
    assert second.status_code == 429
