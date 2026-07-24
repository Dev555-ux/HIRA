"""Tests for the Knowledge Base CRUD API: auth guard, tenant isolation, embeddings."""

import pytest
from fastapi.testclient import TestClient

from app.api.knowledge_base import get_kb_embedding_provider
from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import Business, KbEntry, User
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
    app.dependency_overrides[get_kb_embedding_provider] = lambda: FakeEmbeddingProvider()
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def test_list_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)
    resp = client.get("/api/v1/kb")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_create_indexes_entry_with_embedding(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/kb", headers=_auth(), json={"title": "Hours", "content": "We open at 9am."}
    )

    assert resp.status_code == 201
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["title"] == "Hours"
    assert data[0]["content"] == "We open at 9am."
    stored = db_session.get(KbEntry, data[0]["id"])
    assert stored.embedding is not None
    assert len(stored.embedding) == 384
    app.dependency_overrides.clear()


def test_create_rejects_blank_fields(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post("/api/v1/kb", headers=_auth(), json={"title": "  ", "content": "text"})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_create_rejects_oversized_content(db_session):
    # Regression: content had no max_length — a pathological submission would
    # embed/chunk an unbounded amount of text per request (Sprint 52B, Task 2).
    from app.api.knowledge_base import MAX_KB_CONTENT_LENGTH

    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})

    resp = client.post(
        "/api/v1/kb",
        headers=_auth(),
        json={"title": "Hours", "content": "x" * (MAX_KB_CONTENT_LENGTH + 1)},
    )

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_list_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    db_session.add(KbEntry(business_id=biz_a.id, title="A fact", content="A content"))
    db_session.add(KbEntry(business_id=biz_b.id, title="B fact", content="B content"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/kb", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]
    assert len(data) == 1
    assert data[0]["title"] == "A fact"
    assert body["meta"] == {"total": 1, "limit": 200, "offset": 0}
    app.dependency_overrides.clear()


def test_list_supports_limit_and_offset(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    for i in range(4):
        db_session.add(KbEntry(business_id=biz.id, title=f"fact-{i}", content=f"content {i}"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/kb", params={"limit": 2, "offset": 1}, headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["meta"] == {"total": 4, "limit": 2, "offset": 1}
    app.dependency_overrides.clear()


def test_patch_updates_content_and_reembeds(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    provider = FakeEmbeddingProvider()
    original_vector = provider.embed_documents(["Old content"])[0]
    entry = KbEntry(
        business_id=biz.id, title="Hours", content="Old content", embedding=original_vector
    )
    db_session.add(entry)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch(f"/api/v1/kb/{entry.id}", headers=_auth(), json={"content": "New content"})

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["content"] == "New content"
    db_session.refresh(entry)
    assert list(entry.embedding) != list(original_vector)
    app.dependency_overrides.clear()


def test_patch_title_only_does_not_reembed(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    provider = FakeEmbeddingProvider()
    original_vector = provider.embed_documents(["Some content"])[0]
    entry = KbEntry(
        business_id=biz.id, title="Old title", content="Some content", embedding=original_vector
    )
    db_session.add(entry)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch(f"/api/v1/kb/{entry.id}", headers=_auth(), json={"title": "New title"})

    assert resp.status_code == 200
    db_session.refresh(entry)
    assert entry.title == "New title"
    # pgvector stores embeddings as 4-byte float4, not Python's float64 — a
    # genuine round-trip through the column can lose precision in the last
    # few digits (observed in CI's Postgres though not this sandbox's, same
    # image tag). Exact list equality asserts a bit-for-bit guarantee the
    # storage type was never designed to provide; pytest.approx compares
    # elementwise within a relative tolerance, which is what "the embedding
    # is unchanged" actually means here.
    assert list(entry.embedding) == pytest.approx(list(original_vector))
    app.dependency_overrides.clear()


def test_cannot_patch_another_businesss_entry(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    entry_b = KbEntry(business_id=biz_b.id, title="B fact", content="B content")
    db_session.add(entry_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.patch(f"/api/v1/kb/{entry_b.id}", headers=_auth(), json={"title": "Hijacked"})

    assert resp.status_code == 404
    db_session.refresh(entry_b)
    assert entry_b.title == "B fact"
    app.dependency_overrides.clear()


def test_delete_removes_entry(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    entry = KbEntry(business_id=biz.id, title="Hours", content="We open at 9am.")
    db_session.add(entry)
    db_session.commit()
    entry_id = entry.id

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.delete(f"/api/v1/kb/{entry_id}", headers=_auth())

    assert resp.status_code == 204
    assert db_session.get(KbEntry, entry_id) is None
    app.dependency_overrides.clear()


def test_cannot_delete_another_businesss_entry(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    entry_b = KbEntry(business_id=biz_b.id, title="B fact", content="B content")
    db_session.add(entry_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.delete(f"/api/v1/kb/{entry_b.id}", headers=_auth())

    assert resp.status_code == 404
    assert db_session.get(KbEntry, entry_b.id) is not None
    app.dependency_overrides.clear()


def test_list_excludes_drafts(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.add(KbEntry(business_id=biz.id, title="Live", content="Live content"))
    db_session.add(
        KbEntry(business_id=biz.id, title="Draft", content="Draft content", status="draft")
    )
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/kb", headers=_auth())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    assert body["data"][0]["title"] == "Live"
    assert body["meta"]["total"] == 1
    app.dependency_overrides.clear()


def test_get_drafts_groups_by_import_batch(db_session):
    import uuid

    biz, _ = _seed_business(db_session, "A", "user_a")
    batch_id = uuid.uuid4()
    db_session.add(
        KbEntry(
            business_id=biz.id,
            title="Hours",
            content="Chunk 1",
            status="draft",
            import_batch_id=batch_id,
        )
    )
    db_session.add(
        KbEntry(
            business_id=biz.id,
            title="Hours",
            content="Chunk 2",
            status="draft",
            import_batch_id=batch_id,
        )
    )
    db_session.add(KbEntry(business_id=biz.id, title="Live", content="Live content"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/kb/drafts", headers=_auth())

    assert resp.status_code == 200
    batches = resp.json()["data"]
    assert len(batches) == 1
    assert batches[0]["import_batch_id"] == str(batch_id)
    assert len(batches[0]["entries"]) == 2
    app.dependency_overrides.clear()


def test_get_drafts_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    db_session.add(KbEntry(business_id=biz_b.id, title="B draft", content="x", status="draft"))
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.get("/api/v1/kb/drafts", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"] == []
    app.dependency_overrides.clear()


def test_publish_moves_a_draft_live(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    entry = KbEntry(business_id=biz.id, title="Draft", content="x", status="draft")
    db_session.add(entry)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/kb/{entry.id}/publish", headers=_auth())

    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "published"
    db_session.refresh(entry)
    assert entry.status == "published"
    app.dependency_overrides.clear()


def test_publish_another_businesss_draft_404s(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    entry_b = KbEntry(business_id=biz_b.id, title="Draft", content="x", status="draft")
    db_session.add(entry_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/kb/{entry_b.id}/publish", headers=_auth())

    assert resp.status_code == 404
    db_session.refresh(entry_b)
    assert entry_b.status == "draft"
    app.dependency_overrides.clear()


def test_reject_deletes_the_draft(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    entry = KbEntry(business_id=biz.id, title="Draft", content="x", status="draft")
    db_session.add(entry)
    db_session.commit()
    entry_id = entry.id

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/kb/{entry_id}/reject", headers=_auth())

    assert resp.status_code == 204
    assert db_session.get(KbEntry, entry_id) is None
    app.dependency_overrides.clear()


def test_reject_another_businesss_draft_404s(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    biz_b, _ = _seed_business(db_session, "B", "user_b")
    entry_b = KbEntry(business_id=biz_b.id, title="Draft", content="x", status="draft")
    db_session.add(entry_b)
    db_session.commit()

    client = _client(db_session, claims_for_token=lambda t: {"sub": "user_a"})
    resp = client.post(f"/api/v1/kb/{entry_b.id}/reject", headers=_auth())

    assert resp.status_code == 404
    assert db_session.get(KbEntry, entry_b.id) is not None
    app.dependency_overrides.clear()
