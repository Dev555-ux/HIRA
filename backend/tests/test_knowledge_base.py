"""Tests for KB ingestion + pgvector semantic search (deterministic fake provider)."""

import hashlib

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.knowledge_base import index_entry, retrieve_context, search
from app.models import Business, KbEntry


class FakeEmbeddingProvider(EmbeddingProvider):
    """Deterministic 384-d vectors so identical text -> identical vector.

    Good enough to test the indexing/search plumbing and tenant scoping without
    downloading a real model. Identical strings produce distance 0.
    """

    @property
    def dimension(self) -> int:
        return 384

    def _vec(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.strip().encode()).digest()
        return [digest[i % len(digest)] / 255.0 for i in range(384)]

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


def _business(db, name):
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def test_index_entry_creates_chunk_rows_with_embeddings(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")

    entries = index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider)

    assert len(entries) == 1
    stored = db_session.get(KbEntry, entries[0].id)
    assert stored.embedding is not None
    assert len(stored.embedding) == 384


def test_search_ranks_exact_match_first(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    index_entry(db_session, biz.id, "Hours", "We open at 9am on weekdays.", provider=provider)
    index_entry(db_session, biz.id, "Parking", "Parking is free for patients.", provider=provider)

    results = search(db_session, biz.id, "We open at 9am on weekdays.", provider=provider, k=2)

    assert results[0][1] < 1e-6  # exact-match distance ~0
    assert "9am" in results[0][0].content


def test_search_is_tenant_scoped(db_session):
    provider = FakeEmbeddingProvider()
    biz_a = _business(db_session, "Clinic A")
    biz_b = _business(db_session, "Salon B")
    index_entry(db_session, biz_a.id, "Hours", "We open at 9am.", provider=provider)
    index_entry(db_session, biz_b.id, "Hours", "We open at 9am.", provider=provider)

    a_results = retrieve_context(db_session, biz_a.id, "opening hours", provider=provider, k=10)

    assert len(a_results) == 1
    assert all(e.business_id == biz_a.id for e in a_results)
