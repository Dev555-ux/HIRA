"""Transactional outbox enqueue service (Sprint 64 — ADR-001 / IMP-001, PR 2).

The single, centralized place that turns "I want this work done in the
background" into a durable `job_outbox` row. Everything here is deliberately
*only* about **creation**: there is no worker, no polling, no dispatch, no
retry scheduling, and no locking in this module — those arrive in PR 3
(`app/jobs/worker.py` / `handlers.py`).

The defining property of a transactional outbox is that the job row is written
**inside the caller's own database transaction**, so the job and the business
state that justifies it (a stored Message, an updated Lead, ...) commit
atomically — either both land or neither does. To preserve that guarantee this
module **never commits and never rolls back the caller's transaction**. It only
`flush()`es (to assign the row and surface constraint errors); the caller's
own `commit()` is what makes the job durable. If the caller's transaction rolls
back, the job correctly never existed.

Two entry points, same behaviour:

* `OutboxService(db).enqueue(...)` — the object form (IMP-001's "dedicated
  OutboxService"); construct it around the caller's `Session`.
* `enqueue_job(db, ...)` — a thin module-level function matching the interface
  documented in IMP-001 §4.3, for call sites that prefer a free function
  (e.g. the webhook dual-write branch landing in PR 4).

Idempotency: pass `idempotency_key` to make enqueue safe to call more than once
for the same logical event (e.g. a redelivered webhook). The key is **globally
unique** (see `JobOutbox.idempotency_key`), so callers should namespace it
themselves — e.g. ``f"whatsapp:{message_id}"``. A duplicate is a no-op that
returns ``None`` rather than creating a second job.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.jobs.models import JobOutbox, JobStatus

logger = logging.getLogger(__name__)

# A payload may be given as a plain JSON-safe mapping or as a Pydantic model
# (strongly typed call sites). Both normalise to the JSONB dict the column
# stores; see `_coerce_payload`.
JobPayload = Mapping[str, Any] | BaseModel

# Mirror the column widths declared on JobOutbox so validation fails fast with a
# clear message instead of deferring to a truncation/DB error at flush time.
_MAX_TASK_NAME_LEN = 128
_MAX_QUEUE_NAME_LEN = 64
_MAX_IDEMPOTENCY_KEY_LEN = 256


class OutboxValidationError(ValueError):
    """A job could not be created because its inputs were invalid.

    Subclasses ValueError so existing `except ValueError` handlers keep working,
    matching how the rest of this codebase raises typed-but-standard errors.
    """


def _coerce_payload(payload: JobPayload) -> dict[str, Any]:
    """Normalise a payload to the JSON-safe dict the JSONB column stores.

    Accepts a Pydantic model (serialised in JSON mode, so nested UUID/datetime
    become strings) or a mapping (must already contain JSON-safe values). Raises
    OutboxValidationError for anything else, or for a mapping that isn't
    JSON-serialisable — caught here rather than as an opaque driver error at
    flush.
    """
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    if isinstance(payload, Mapping):
        coerced = dict(payload)
        try:
            json.dumps(coerced)
        except (TypeError, ValueError) as exc:
            raise OutboxValidationError(
                "payload must be JSON-serialisable (pass a Pydantic model or a "
                "dict of JSON-safe values)"
            ) from exc
        return coerced
    raise OutboxValidationError("payload must be a mapping or a Pydantic model")


class OutboxService:
    """Creates transactional outbox jobs inside the caller's transaction.

    Construct one around the `Session` the caller is already using for its
    business writes, so the enqueued job shares that transaction:

        service = OutboxService(db)
        service.enqueue(business_id=..., task_name="generate_ai_reply", payload=...)
        # ... caller's own db.commit() persists the job atomically with its work

    The service holds no state beyond that session and is cheap to construct
    per operation.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def enqueue(
        self,
        *,
        business_id: uuid.UUID,
        task_name: str,
        payload: JobPayload,
        queue_name: str = "default",
        idempotency_key: str | None = None,
        run_at: datetime | None = None,
        max_attempts: int = 5,
    ) -> JobOutbox | None:
        """Create one PENDING `job_outbox` row in the caller's transaction.

        Returns the created `JobOutbox`, or ``None`` when `idempotency_key` is
        given and a job with that key already exists (a deduplicated no-op).

        The row is `flush()`ed but **not committed** — the caller's own commit
        makes it durable, atomically with whatever business state it wrote. The
        server clock (`func.now()`) supplies `created_at` / `updated_at`, and
        `run_at` when not overridden, so every job's timestamps come from the
        same source as every other table in this schema.

        Validation (raises `OutboxValidationError`):
        * `task_name` — required, non-blank, <= 128 chars
        * `queue_name` — non-blank, <= 64 chars
        * `payload` — a mapping or Pydantic model of JSON-safe values
        * `idempotency_key` — if given, non-blank, <= 256 chars
        * `max_attempts` — >= 1
        """
        db = self._db

        business_id = self._validate_business_id(business_id)
        task_name = self._validate_str("task_name", task_name, _MAX_TASK_NAME_LEN)
        queue_name = self._validate_str("queue_name", queue_name, _MAX_QUEUE_NAME_LEN)
        if max_attempts < 1:
            raise OutboxValidationError("max_attempts must be >= 1")
        if idempotency_key is not None:
            idempotency_key = self._validate_str(
                "idempotency_key", idempotency_key, _MAX_IDEMPOTENCY_KEY_LEN
            )
        stored_payload = _coerce_payload(payload)

        # Fast path for the common "already enqueued" case: a plain lookup, no
        # failed INSERT, no savepoint churn. The savepoint below is only there
        # for the genuine race (a concurrent inserter between here and flush).
        if idempotency_key is not None:
            existing = self._find_by_idempotency_key(idempotency_key)
            if existing is not None:
                logger.info(
                    "Outbox job deduplicated (existing job %s, task=%s queue=%s "
                    "business=%s idempotency_key=%s)",
                    existing.id,
                    task_name,
                    queue_name,
                    business_id,
                    idempotency_key,
                )
                return None

        job = JobOutbox(
            business_id=business_id,
            task_name=task_name,
            payload=stored_payload,
            queue_name=queue_name,
            status=JobStatus.PENDING,
            max_attempts=max_attempts,
            idempotency_key=idempotency_key,
        )
        if run_at is not None:
            job.run_at = run_at

        try:
            # A SAVEPOINT is essential, not decorative: in Postgres any
            # constraint violation aborts the *entire* transaction, which would
            # destroy the caller's un-committed business writes. begin_nested()
            # scopes the failure to this INSERT so the caller's transaction
            # survives a duplicate key (or any other integrity error). The add()
            # MUST be inside the savepoint block — otherwise a failed flush dooms
            # the enclosing session transaction (SQLAlchemy 2.0 semantics).
            with db.begin_nested():
                db.add(job)
                db.flush()
        except IntegrityError:
            if job in db:
                db.expunge(job)
            if idempotency_key is not None and self._find_by_idempotency_key(idempotency_key):
                logger.info(
                    "Outbox job deduplicated on race (task=%s queue=%s business=%s "
                    "idempotency_key=%s)",
                    task_name,
                    queue_name,
                    business_id,
                    idempotency_key,
                )
                return None
            # Not an idempotency conflict (e.g. an unknown business_id FK) — the
            # savepoint has already protected the caller's transaction; surface
            # the real error rather than silently swallowing it.
            raise

        db.refresh(job)
        logger.info(
            "Enqueued outbox job %s (task=%s queue=%s business=%s idempotency_key=%s)",
            job.id,
            task_name,
            queue_name,
            business_id,
            idempotency_key,
        )
        return job

    def _find_by_idempotency_key(self, idempotency_key: str) -> JobOutbox | None:
        return self._db.scalars(
            select(JobOutbox).where(JobOutbox.idempotency_key == idempotency_key)
        ).first()

    @staticmethod
    def _validate_business_id(business_id: uuid.UUID) -> uuid.UUID:
        if not isinstance(business_id, uuid.UUID):
            raise OutboxValidationError("business_id must be a UUID")
        return business_id

    @staticmethod
    def _validate_str(field: str, value: str, max_len: int) -> str:
        if not isinstance(value, str) or not value.strip():
            raise OutboxValidationError(f"{field} is required and must be non-empty")
        value = value.strip()
        if len(value) > max_len:
            raise OutboxValidationError(f"{field} must be at most {max_len} characters")
        return value


def enqueue_job(
    db: Session,
    *,
    task_name: str,
    payload: JobPayload,
    business_id: uuid.UUID,
    queue_name: str = "default",
    idempotency_key: str | None = None,
    run_at: datetime | None = None,
    max_attempts: int = 5,
) -> JobOutbox | None:
    """Enqueue a background job inside the caller's active database transaction.

    Thin free-function form of `OutboxService.enqueue` matching the interface in
    IMP-001 §4.3. Returns the created `JobOutbox`, or ``None`` if the call was a
    no-op via an existing `idempotency_key`. See `OutboxService.enqueue` for the
    full contract, validation rules, and transactional guarantees.
    """
    return OutboxService(db).enqueue(
        business_id=business_id,
        task_name=task_name,
        payload=payload,
        queue_name=queue_name,
        idempotency_key=idempotency_key,
        run_at=run_at,
        max_attempts=max_attempts,
    )
