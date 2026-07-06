"""Tests for POST /api/v1/onboarding/playground/message: auth, tenant scoping,
and that it's a thin layer over the unmodified AI pipeline (mocked here)."""

from fastapi.testclient import TestClient

from app.ai.knowledge_base import index_entry
from app.ai.llm.mock import MockProvider
from app.auth.dependencies import get_token_verifier
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


def test_playground_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.post("/api/v1/onboarding/playground/message", json={"message": "hi"})
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_playground_returns_reply_and_retrieved_kb_entries(db_session, monkeypatch):
    biz, _ = _seed_business(db_session, "A", "user_a")
    index_entry(
        db_session, biz.id, "Hours", "We open at 9am.", provider=FakeEmbeddingProvider()
    )
    db_session.commit()
    _mock_providers(monkeypatch, fixed_reply="We're open at 9am!")
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/onboarding/playground/message",
        headers=_auth(),
        json={"message": "what time do you open?"},
    )

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["reply"] == "We're open at 9am!"
    assert data["model"] == "mock-1"
    assert len(data["retrieved"]) >= 1
    assert data["retrieved"][0]["title"] == "Hours"
    app.dependency_overrides.clear()


def test_playground_rejects_blank_message(db_session, monkeypatch):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    _mock_providers(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "   "}
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_playground_is_scoped_to_calling_business(db_session, monkeypatch):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    index_entry(
        db_session, biz_a.id, "Secret A", "Only business A knows this.", provider=FakeEmbeddingProvider()
    )
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    index_entry(
        db_session, biz_b.id, "Secret B", "Only business B knows this.", provider=FakeEmbeddingProvider()
    )
    db_session.commit()
    _mock_providers(monkeypatch)
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/onboarding/playground/message", headers=_auth(), json={"message": "any secrets?"}
    )

    assert resp.status_code == 200
    titles = {e["title"] for e in resp.json()["data"]["retrieved"]}
    assert "Secret B" not in titles
    app.dependency_overrides.clear()
