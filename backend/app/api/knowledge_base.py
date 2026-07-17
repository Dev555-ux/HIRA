"""Knowledge Base API (/api/v1/kb) — manual entry + single-page website import.

An owner types a title + fact, or submits a URL; either way the content is
chunked and embedded via the existing `EmbeddingProvider` and stored as one or
more `kb_entries` rows (see app/ai/knowledge_base.py). Website import
(`POST /website`) fetches and cleans exactly one page (app/ai/web_import.py)
and indexes it immediately — no multi-page crawl, no PDF extraction, and no
draft/review staging before content goes live. That fuller pipeline
(`kb_entry_drafts`, owner approval before anything reaches this table) is
designed in ONBOARDING_ARCHITECTURE.md Milestone B / TODOS.md ONBOARD-B but
not built; this endpoint is a smaller, direct-to-live alternative pending a
decision on whether a review step is still wanted before real customers see
imported content.

Every route sits behind `get_current_principal`, same as dashboard.py, and
every query is tenant-scoped via `tenant_query`/`get_scoped` — a business can
only ever see or modify its own KB entries.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider, get_embedding_provider
from app.ai.knowledge_base import delete_entry, index_entry, update_entry
from app.ai.web_import import WebImportError, fetch_page
from app.auth.dependencies import Principal, get_current_principal
from app.core.config import settings
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.db.tenant import tenant_query
from app.models import KbEntry

router = APIRouter(prefix="/api/v1/kb", tags=["knowledge-base"])

# Sprint 36: same guard-rail rationale as dashboard.py's /pending — a cap
# against a truly unbounded scan, defaulted high enough that today's
# "see the whole KB" behavior is unchanged for any realistic business.
DEFAULT_KB_LIMIT = 200
MAX_KB_LIMIT = 200

# Sprint 52B: title matches KbEntry.title's own String(512) column — without
# this, an oversized title fails at commit with a raw DB error instead of a
# clean 422. content has no DB-side bound (KbEntry.content is Text, and
# index_entry() already chunks arbitrarily long input into multiple rows —
# see app/ai/knowledge_base.py), so this is purely a cost/abuse guard: a
# manually-typed "fact" is meant to be a short snippet, not a document (that's
# what /website is for, already scoped to one page) — 20k chars bounds the
# embedding cost of a single submission without constraining any realistic
# fact.
MAX_KB_TITLE_LENGTH = 512
MAX_KB_CONTENT_LENGTH = 20_000


class CreateKbEntryRequest(BaseModel):
    title: str = Field(max_length=MAX_KB_TITLE_LENGTH)
    content: str = Field(max_length=MAX_KB_CONTENT_LENGTH)


class UpdateKbEntryRequest(BaseModel):
    title: str | None = Field(default=None, max_length=MAX_KB_TITLE_LENGTH)
    content: str | None = Field(default=None, max_length=MAX_KB_CONTENT_LENGTH)


class ImportWebsiteRequest(BaseModel):
    url: HttpUrl


def get_kb_embedding_provider() -> EmbeddingProvider:
    """The embedding provider used for KB indexing. Overridable in tests."""
    return get_embedding_provider()


def get_web_page_fetcher() -> Callable[[str], tuple[str, str]]:
    """Fetches (title, readable_text) for a URL. Overridable in tests."""
    return fetch_page


def _serialize(entry: KbEntry) -> dict:
    return {
        "id": str(entry.id),
        "title": entry.title,
        "content": entry.content,
        "created_at": entry.created_at.isoformat(),
        "updated_at": entry.updated_at.isoformat(),
    }


@router.get("")
def list_entries(
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    limit: int = Query(default=DEFAULT_KB_LIMIT, ge=1, le=MAX_KB_LIMIT),
    offset: int = Query(default=0, ge=0),
) -> dict:
    base_stmt = tenant_query(KbEntry, principal.business_id)
    total = db.scalar(select(func.count()).select_from(base_stmt.subquery()))

    stmt = base_stmt.order_by(KbEntry.title, KbEntry.created_at).limit(limit).offset(offset)
    rows = db.scalars(stmt).all()
    return {
        "data": [_serialize(e) for e in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: settings.rate_limit_kb_upload)
def create_entry(
    request: Request,
    payload: CreateKbEntryRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_kb_embedding_provider),
) -> dict:
    title = payload.title.strip()
    content = payload.content.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title is required")
    if not content:
        raise HTTPException(status_code=422, detail="Content is required")

    entries = index_entry(db, principal.business_id, title, content, provider=provider)
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return {"data": [_serialize(e) for e in entries]}


@router.post("/website", status_code=status.HTTP_201_CREATED)
@limiter.limit(lambda: settings.rate_limit_kb_upload)
def import_website(
    request: Request,
    payload: ImportWebsiteRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_kb_embedding_provider),
    fetch: Callable[[str], tuple[str, str]] = Depends(get_web_page_fetcher),
) -> dict:
    url = str(payload.url)
    try:
        title, text = fetch(url)
    except WebImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not text.strip():
        raise HTTPException(status_code=422, detail="No readable content found at URL")

    entries = index_entry(db, principal.business_id, title or url, text, provider=provider)
    db.commit()
    # `entries` (not just the count) lets the frontend show what was actually
    # learned, not just a number — same objects index_entry already built,
    # just also serialized here rather than discarded.
    return {
        "pages_imported": 1,
        "entries_created": len(entries),
        "entries": [{"id": str(e.id), "title": e.title, "content": e.content} for e in entries],
    }


@router.patch("/{entry_id}")
def patch_entry(
    entry_id: uuid.UUID,
    payload: UpdateKbEntryRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
    provider: EmbeddingProvider = Depends(get_kb_embedding_provider),
) -> dict:
    title = payload.title.strip() if payload.title is not None else None
    content = payload.content.strip() if payload.content is not None else None
    if payload.title is not None and not title:
        raise HTTPException(status_code=422, detail="Title cannot be blank")
    if payload.content is not None and not content:
        raise HTTPException(status_code=422, detail="Content cannot be blank")
    if title is None and content is None:
        raise HTTPException(status_code=422, detail="Nothing to update")

    entry = update_entry(
        db, principal.business_id, entry_id, title=title, content=content, provider=provider
    )
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.commit()
    db.refresh(entry)
    return {"data": _serialize(entry)}


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_entry(
    entry_id: uuid.UUID,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_entry(db, principal.business_id, entry_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    db.commit()
