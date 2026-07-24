"""Tests for KB ingestion + pgvector semantic search (deterministic fake provider)."""

import hashlib

from app.ai.embeddings.base import EmbeddingProvider
from app.ai.knowledge_base import (
    has_any_entries,
    index_entry,
    list_drafts,
    publish_entry,
    retrieve_context,
    search,
)
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


def test_has_any_entries_false_for_a_business_with_no_kb(db_session):
    biz = _business(db_session, "Clinic A")
    db_session.flush()

    assert has_any_entries(db_session, biz.id) is False


def test_has_any_entries_true_once_a_single_entry_exists(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")

    index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider)

    assert has_any_entries(db_session, biz.id) is True


def test_has_any_entries_is_tenant_scoped(db_session):
    provider = FakeEmbeddingProvider()
    biz_a = _business(db_session, "Clinic A")
    biz_b = _business(db_session, "Clinic B")

    index_entry(db_session, biz_a.id, "Hours", "We open at 9am.", provider=provider)

    assert has_any_entries(db_session, biz_a.id) is True
    assert has_any_entries(db_session, biz_b.id) is False


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


def test_index_entry_defaults_to_published_with_no_batch(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")

    entries = index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider)

    assert entries[0].status == "published"
    assert entries[0].import_batch_id is None


def test_index_entry_can_create_a_draft_batch(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    import uuid

    batch_id = uuid.uuid4()
    entries = index_entry(
        db_session,
        biz.id,
        "Hours",
        "We open at 9am.\n\nWe close at 5pm.",
        provider=provider,
        status="draft",
        import_batch_id=batch_id,
    )

    assert len(entries) == 2
    assert all(e.status == "draft" for e in entries)
    assert all(e.import_batch_id == batch_id for e in entries)


def test_search_never_returns_draft_entries(db_session):
    """A draft must never ground a live customer-facing answer (DEC-039) —
    even when it's the closest possible match."""
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    index_entry(
        db_session,
        biz.id,
        "Hours",
        "We open at 9am on weekdays.",
        provider=provider,
        status="draft",
    )

    results = retrieve_context(db_session, biz.id, "We open at 9am on weekdays.", provider=provider)

    assert results == []


def test_search_returns_published_entries_alongside_excluded_drafts(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider)
    index_entry(
        db_session, biz.id, "Draft note", "We open at 9am.", provider=provider, status="draft"
    )

    results = retrieve_context(db_session, biz.id, "We open at 9am.", provider=provider, k=10)

    assert len(results) == 1
    assert results[0].status == "published"


def test_has_any_entries_ignores_drafts(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    index_entry(db_session, biz.id, "Hours", "We open at 9am.", provider=provider, status="draft")

    assert has_any_entries(db_session, biz.id) is False


def test_list_drafts_returns_only_drafts_tenant_scoped(db_session):
    provider = FakeEmbeddingProvider()
    biz_a = _business(db_session, "Clinic A")
    biz_b = _business(db_session, "Clinic B")
    index_entry(db_session, biz_a.id, "Published", "Live fact.", provider=provider)
    index_entry(db_session, biz_a.id, "Draft", "New fact.", provider=provider, status="draft")
    index_entry(
        db_session, biz_b.id, "Other draft", "Other fact.", provider=provider, status="draft"
    )

    drafts = list_drafts(db_session, biz_a.id)

    assert len(drafts) == 1
    assert drafts[0].title == "Draft"


def test_publish_entry_moves_draft_to_published(db_session):
    provider = FakeEmbeddingProvider()
    biz = _business(db_session, "Clinic A")
    entries = index_entry(
        db_session, biz.id, "Draft", "New fact.", provider=provider, status="draft"
    )

    published = publish_entry(db_session, biz.id, entries[0].id)

    assert published.status == "published"
    assert list_drafts(db_session, biz.id) == []


def test_publish_entry_is_tenant_scoped(db_session):
    provider = FakeEmbeddingProvider()
    biz_a = _business(db_session, "Clinic A")
    biz_b = _business(db_session, "Clinic B")
    entries = index_entry(
        db_session, biz_b.id, "Draft", "New fact.", provider=provider, status="draft"
    )

    result = publish_entry(db_session, biz_a.id, entries[0].id)

    assert result is None
