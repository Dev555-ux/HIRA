"""Tests for the website import API: POST /api/v1/kb/website.

The HTTP fetch itself is covered in tests/test_web_import.py; here the page
fetcher is stubbed via dependency override (same pattern as
`get_kb_embedding_provider`) so these tests exercise auth, tenant scoping, and
that chunking/indexing/response shape are wired correctly — no real network.
"""

from app.api.knowledge_base import get_kb_embedding_provider, get_web_page_fetcher
from app.auth.dependencies import get_token_verifier
from app.db.session import get_db
from app.main import app
from app.models import KbEntry
from tests.test_knowledge_base import FakeEmbeddingProvider
from tests.test_knowledge_base_api import _auth, _seed_business

from fastapi.testclient import TestClient


def _client(db_session, *, claims_for_token, fetch_page):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    app.dependency_overrides[get_kb_embedding_provider] = lambda: FakeEmbeddingProvider()
    app.dependency_overrides[get_web_page_fetcher] = lambda: fetch_page
    return TestClient(app)


def test_import_requires_authentication(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    resp = client.post("/api/v1/kb/website", json={"url": "https://example.com"})

    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_import_rejects_invalid_url(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(
        db_session, claims_for_token=lambda t: {"sub": "user_a"}, fetch_page=lambda url: ("t", "x")
    )

    resp = client.post("/api/v1/kb/website", headers=_auth(), json={"url": "not-a-url"})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_import_indexes_extracted_text_and_reports_counts(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()

    def fake_fetch(url):
        assert url == "https://example.com/hours"
        return "Opening Hours", "We open at 9am.\n\nWe close at 5pm."

    client = _client(
        db_session, claims_for_token=lambda t: {"sub": "user_a"}, fetch_page=fake_fetch
    )

    resp = client.post(
        "/api/v1/kb/website", headers=_auth(), json={"url": "https://example.com/hours"}
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["pages_imported"] == 1
    assert body["entries_created"] == 2
    # The response includes what was actually imported, not just a count —
    # this is what the frontend's post-import summary shows the owner.
    assert {e["title"] for e in body["entries"]} == {"Opening Hours"}
    assert {e["content"] for e in body["entries"]} == {"We open at 9am.", "We close at 5pm."}
    stored = db_session.query(KbEntry).filter_by(business_id=biz.id).all()
    assert len(stored) == 2
    assert {e.title for e in stored} == {"Opening Hours"}
    assert {e.content for e in stored} == {"We open at 9am.", "We close at 5pm."}
    assert all(e.embedding is not None for e in stored)
    app.dependency_overrides.clear()


def test_import_creates_drafts_sharing_one_batch_id_not_published(db_session):
    """DEC-039: an import must never be immediately live — it's a draft
    pending review until explicitly published, unlike a manual entry."""
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()

    def fake_fetch(url):
        return "Opening Hours", "We open at 9am.\n\nWe close at 5pm."

    client = _client(
        db_session, claims_for_token=lambda t: {"sub": "user_a"}, fetch_page=fake_fetch
    )

    resp = client.post("/api/v1/kb/website", headers=_auth(), json={"url": "https://example.com"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["import_batch_id"] is not None
    stored = db_session.query(KbEntry).filter_by(business_id=biz.id).all()
    assert len(stored) == 2
    assert all(e.status == "draft" for e in stored)
    assert len({e.import_batch_id for e in stored}) == 1
    assert str(stored[0].import_batch_id) == body["import_batch_id"]

    # A draft import must not appear in the live KB list...
    list_resp = client.get("/api/v1/kb", headers=_auth())
    assert list_resp.json()["data"] == []
    # ...but must appear in the drafts queue, grouped under that batch.
    drafts_resp = client.get("/api/v1/kb/drafts", headers=_auth())
    batches = drafts_resp.json()["data"]
    assert len(batches) == 1
    assert batches[0]["import_batch_id"] == body["import_batch_id"]
    assert len(batches[0]["entries"]) == 2
    app.dependency_overrides.clear()


def test_import_is_tenant_scoped(db_session):
    biz_a, _ = _seed_business(db_session, "A", "user_a")
    _seed_business(db_session, "B", "user_b")
    db_session.commit()

    client = _client(
        db_session,
        claims_for_token=lambda t: {"sub": "user_a"},
        fetch_page=lambda url: ("Title", "Some page content."),
    )

    resp = client.post("/api/v1/kb/website", headers=_auth(), json={"url": "https://example.com"})

    assert resp.status_code == 201
    stored = db_session.query(KbEntry).all()
    assert len(stored) == 1
    assert stored[0].business_id == biz_a.id
    app.dependency_overrides.clear()


def test_import_rejects_page_with_no_readable_content(db_session):
    _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(
        db_session,
        claims_for_token=lambda t: {"sub": "user_a"},
        fetch_page=lambda url: ("Empty", "   "),
    )

    resp = client.post("/api/v1/kb/website", headers=_auth(), json={"url": "https://example.com"})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_import_surfaces_fetch_failure_as_422(db_session):
    from app.ai.web_import import WebImportError

    _seed_business(db_session, "A", "user_a")
    db_session.commit()

    def failing_fetch(url):
        raise WebImportError("Could not fetch it")

    client = _client(
        db_session, claims_for_token=lambda t: {"sub": "user_a"}, fetch_page=failing_fetch
    )

    resp = client.post("/api/v1/kb/website", headers=_auth(), json={"url": "https://example.com"})

    assert resp.status_code == 422
    app.dependency_overrides.clear()


def test_import_falls_back_to_url_as_title_when_page_has_none(db_session):
    biz, _ = _seed_business(db_session, "A", "user_a")
    db_session.commit()
    client = _client(
        db_session,
        claims_for_token=lambda t: {"sub": "user_a"},
        fetch_page=lambda url: ("", "Some content here."),
    )

    resp = client.post(
        "/api/v1/kb/website", headers=_auth(), json={"url": "https://example.com/page"}
    )

    assert resp.status_code == 201
    stored = db_session.query(KbEntry).filter_by(business_id=biz.id).one()
    assert stored.title == "https://example.com/page"
    app.dependency_overrides.clear()
