"""Multi-tenant scoping helpers.

Every business-owned row carries a `business_id`. These helpers make it hard to
*forget* to scope a query to the calling business — the single most important
safeguard against cross-tenant data leaks (ARCHITECTURE.md §10).

Use `tenant_query` to build any SELECT that must be limited to one business, and
`get_scoped` to fetch a single row by id within a business. A model without a
`business_id` column raises immediately, rather than silently returning
everything.
"""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


def _require_business_scope(model: type[ModelT]) -> None:
    if not hasattr(model, "business_id"):
        raise ValueError(f"{model.__name__} has no business_id column and cannot be tenant-scoped")


def tenant_query(model: type[ModelT], business_id: uuid.UUID) -> Select[tuple[ModelT]]:
    """Return a SELECT for `model` restricted to a single business."""
    _require_business_scope(model)
    return select(model).where(model.business_id == business_id)


def get_scoped(
    db: Session, model: type[ModelT], business_id: uuid.UUID, row_id: uuid.UUID
) -> ModelT | None:
    """Fetch one row by id, but only if it belongs to `business_id` (else None)."""
    _require_business_scope(model)
    return db.scalars(
        select(model).where(model.id == row_id, model.business_id == business_id)
    ).first()
