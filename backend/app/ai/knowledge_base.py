"""Knowledge-base ingestion and semantic retrieval.

Ingestion chunks a document, embeds each chunk, and stores one `kb_entries`
row per chunk (scoped to a business). Retrieval embeds the query and runs a
pgvector cosine-similarity search, scoped to the same business.

Everything here depends only on the `EmbeddingProvider` interface, so the
embedding backend is swappable by config (see app/ai/embeddings). All queries
are tenant-scoped by `business_id` — a business can only ever see its own KB.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.chunking import chunk_text
from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.db.tenant import get_scoped
from app.models import KbEntry

logger = logging.getLogger(__name__)


def index_entry(
    db: Session,
    business_id: uuid.UUID,
    title: str,
    content: str,
    *,
    provider: EmbeddingProvider | None = None,
) -> list[KbEntry]:
    """Chunk + embed `content` and store one KB row per chunk. Returns the rows."""
    provider = provider or get_embedding_provider()
    chunks = chunk_text(content)
    if not chunks:
        return []

    vectors = provider.embed_documents(chunks)
    entries = [
        KbEntry(business_id=business_id, title=title, content=chunk, embedding=vector)
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]
    db.add_all(entries)
    db.flush()
    logger.info("Indexed %d KB chunk(s) for business %s", len(entries), business_id)
    return entries


def update_entry(
    db: Session,
    business_id: uuid.UUID,
    entry_id: uuid.UUID,
    *,
    title: str | None = None,
    content: str | None = None,
    provider: EmbeddingProvider | None = None,
) -> KbEntry | None:
    """Update a KB entry's title/content, tenant-scoped. Returns None if not found.

    Re-embeds only when `content` actually changes (title-only edits skip the
    embedding call). Unlike `index_entry`, this does not re-chunk — it updates
    the single row in place, which is correct for manual entries that are
    already one chunk (the common case) and an accepted simplification for the
    rare manually-edited multi-chunk entry (each chunk stays independently
    editable).
    """
    entry = get_scoped(db, KbEntry, business_id, entry_id)
    if entry is None:
        return None
    if title is not None:
        entry.title = title
    if content is not None and content != entry.content:
        provider = provider or get_embedding_provider()
        entry.content = content
        entry.embedding = provider.embed_documents([content])[0]
    db.flush()
    return entry


def delete_entry(db: Session, business_id: uuid.UUID, entry_id: uuid.UUID) -> bool:
    """Delete a KB entry, tenant-scoped. Returns False if it doesn't exist for this business."""
    entry = get_scoped(db, KbEntry, business_id, entry_id)
    if entry is None:
        return False
    db.delete(entry)
    db.flush()
    return True


def search(
    db: Session,
    business_id: uuid.UUID,
    query: str,
    *,
    provider: EmbeddingProvider | None = None,
    k: int = 5,
) -> list[tuple[KbEntry, float]]:
    """Return up to `k` (entry, cosine_distance) pairs for this business, nearest first."""
    provider = provider or get_embedding_provider()
    query_vector = provider.embed_query(query)
    distance = KbEntry.embedding.cosine_distance(query_vector).label("distance")
    stmt = (
        select(KbEntry, distance)
        .where(KbEntry.business_id == business_id)
        .order_by(distance)
        .limit(k)
    )
    return [(entry, float(dist)) for entry, dist in db.execute(stmt).all()]


def retrieve_context(
    db: Session,
    business_id: uuid.UUID,
    query: str,
    *,
    provider: EmbeddingProvider | None = None,
    k: int = 5,
) -> list[KbEntry]:
    """Return the most relevant KB entries to ground a response."""
    return [entry for entry, _distance in search(db, business_id, query, provider=provider, k=k)]
