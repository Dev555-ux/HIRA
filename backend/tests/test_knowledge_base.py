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


class _DirectionalEmbeddingProvider(EmbeddingProvider):
    """Vectors with an exactly known cosine distance from one another —
    unlike FakeEmbeddingProvider's hashed vectors (which all land close
    together in the positive orthant, so they can't exercise a distance
    threshold meaningfully), this can produce a genuinely orthogonal
    (distance 1.0) or genuinely close (distance ~0.05) query on demand."""

    @property
    def dimension(self) -> int:
        return 384

    def _unit(self, i: int) -> list[float]:
        vec = [0.0] * 384
        vec[i] = 1.0
        return vec

    def embed_documents(self, texts):
        return [self._unit(0) for _ in texts]  # every doc lives on axis 0

    def embed_query(self, text):
        if text == "relevant":
            vec = self._unit(0)
            vec[1] = 0.05  # nudged slightly off-axis, still ~0 distance
            return vec
        return self._unit(1)  # "irrelevant" — orthogonal, cosine distance 1.0


def test_search_drops_results_below_the_relevance_bar(db_session):
    """AI-2: a query with nothing genuinely relevant in the KB must not
    ground a reply in the nearest-by-coincidence rows."""
    provider = _DirectionalEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider)

    relevant = retrieve_context(db_session, biz.id, "relevant", provider=provider, k=5)
    irrelevant = retrieve_context(db_session, biz.id, "irrelevant", provider=provider, k=5)

    assert len(relevant) == 1
    assert irrelevant == []


def test_search_max_distance_is_configurable(db_session):
    provider = _DirectionalEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider)

    # The orthogonal ("irrelevant") query has cosine distance exactly 1.0 —
    # raising max_distance past that must let it back in.
    results = search(db_session, biz.id, "irrelevant", provider=provider, k=5, max_distance=1.5)

    assert len(results) == 1
