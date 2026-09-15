"""Operational queries & manual recovery for the transactional outbox
(Sprint 64 — ADR-001 / IMP-001, PR 5).

Read-side visibility (queue health metrics, job listing, job detail) and the one
mutation the outbox needs a human for: manually re-queuing a job that has
exhausted its retries (DEAD_LETTER) or failed permanently (FAILED). The worker
never performs FAILED/DEAD_LETTER -> PENDING itself (PR 3 left it out on
purpose); this is where an operator does it deliberately.

Kept out of the API layer so the logic is HTTP-agnostic and unit-testable, and
kept in `app/jobs/` so every outbox concern lives in one package. The API router
(`app/api/founder_ops.py`) is a thin adapter that maps the typed errors below to
HTTP status codes.

Everything here is cross-tenant by design — the outbox is a system-wide
subsystem operated by the founder, not scoped to one business.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.time import to_iso_utc
from app.jobs.models import JobOutbox, JobStatus

# Only these two terminal-failure states can be manually re-queued. A PENDING or
# PROCESSING job is already (or about to be) worked; a COMPLETED one is done.
RETRYABLE_STATUSES = (JobStatus.FAILED, JobStatus.DEAD_LETTER)


class JobNotFoundError(Exception):
    """No job_outbox row exists for the given id."""


class InvalidRetryStateError(Exception):
    """The job exists but its current status cannot be manually retried."""

    def __init__(self, current_status: JobStatus) -> None:
        self.current_status = current_status
        super().__init__(
            f"Job in status {current_status.value!r} cannot be retried; "
            f"only {[s.value for s in RETRYABLE_STATUSES]} are retryable"
        )


def _utcnow() -> datetime:
    # job_outbox timestamps are timezone-aware (TIMESTAMP WITH TIME ZONE).
    return datetime.now(timezone.utc)


def get_job_metrics(db: Session) -> dict:
    """Queue-health snapshot: a count per status plus the age of the oldest
    still-open PENDING / PROCESSING job.

    Ages are computed with the *database* clock (``func.now()``) so they can't be
    thrown off by app/DB clock skew — a lagging queue or a stuck worker shows up
    honestly. Each age is None when there is no job in that state.
    """
    count_rows = db.execute(select(JobOutbox.status, func.count()).group_by(JobOutbox.status)).all()
    counts = {status.value: n for status, n in count_rows}

    # Oldest PENDING by created_at (how long the oldest unfinished job has waited)
    # and oldest PROCESSING by locked_at (how long the longest in-flight/stuck job
    # has been held) — the two numbers an operator watches for backlog / zombies.
    oldest_pending_age = db.scalar(
        select(func.extract("epoch", func.now() - func.min(JobOutbox.created_at))).where(
            JobOutbox.status == JobStatus.PENDING
        )
    )
    oldest_processing_age = db.scalar(
        select(func.extract("epoch", func.now() - func.min(JobOutbox.locked_at))).where(
            JobOutbox.status == JobStatus.PROCESSING
        )
    )

    return {
        "pending_count": counts.get(JobStatus.PENDING.value, 0),
        "processing_count": counts.get(JobStatus.PROCESSING.value, 0),
        "completed_count": counts.get(JobStatus.COMPLETED.value, 0),
        "failed_count": counts.get(JobStatus.FAILED.value, 0),
        "dead_letter_count": counts.get(JobStatus.DEAD_LETTER.value, 0),
        "oldest_pending_age_seconds": _as_float(oldest_pending_age),
        "oldest_processing_age_seconds": _as_float(oldest_processing_age),
    }


def _filtered(stmt: Select, status: JobStatus | None, queue_name: str | None) -> Select:
    if status is not None:
        stmt = stmt.where(JobOutbox.status == status)
    if queue_name is not None:
        stmt = stmt.where(JobOutbox.queue_name == queue_name)
    return stmt


def list_jobs(
    db: Session,
    *,
    status: JobStatus | None = None,
    queue_name: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Newest-first page of jobs, optionally filtered by status and/or queue.

    Returns the page plus `total` (rows matching the filter, ignoring
    limit/offset) so a caller can drive pagination.
    """
    total = db.scalar(_filtered(select(func.count()).select_from(JobOutbox), status, queue_name))
    stmt = _filtered(select(JobOutbox), status, queue_name)
    jobs = db.scalars(stmt.order_by(JobOutbox.created_at.desc()).limit(limit).offset(offset)).all()
    return {
        "jobs": [_job_summary(job) for job in jobs],
        "total": int(total or 0),
        "limit": limit,
        "offset": offset,
    }


def get_job(db: Session, job_id: uuid.UUID) -> dict | None:
    """Complete detail for one job, or None if it doesn't exist."""
    job = db.get(JobOutbox, job_id)
    return _job_detail(job) if job is not None else None


def retry_job(db: Session, job_id: uuid.UUID) -> dict:
    """Manually re-queue a FAILED or DEAD_LETTER job: reset it to a clean PENDING
    so a worker picks it up again immediately.

    Raises JobNotFoundError if the id is unknown, or InvalidRetryStateError if
    the job is PENDING / PROCESSING / COMPLETED (nothing to recover).
    """
    job = db.get(JobOutbox, job_id)
    if job is None:
        raise JobNotFoundError(str(job_id))
    if job.status not in RETRYABLE_STATUSES:
        raise InvalidRetryStateError(job.status)

    job.status = JobStatus.PENDING
    job.attempts = 0
    job.run_at = _utcnow()
    job.last_error = None
    # A terminal-failure job already has these cleared, but reset defensively so a
    # retried job never carries a stale lock stamp.
    job.locked_at = None
    job.locked_by = None
    job.updated_at = _utcnow()

    db.commit()
    db.refresh(job)
    return _job_detail(job)


def _job_summary(job: JobOutbox) -> dict:
    """The list-row shape (PR 5 spec)."""
    return {
        "id": str(job.id),
        "task_name": job.task_name,
        "status": job.status.value,
        "attempts": job.attempts,
        "max_attempts": job.max_attempts,
        "created_at": to_iso_utc(job.created_at),
        "updated_at": to_iso_utc(job.updated_at),
        "run_at": to_iso_utc(job.run_at),
        "locked_by": job.locked_by,
        "last_error": job.last_error,
    }


def _job_detail(job: JobOutbox) -> dict:
    """The summary plus everything else on the row."""
    return {
        **_job_summary(job),
        "business_id": str(job.business_id),
        "queue_name": job.queue_name,
        "payload": job.payload,
        "idempotency_key": job.idempotency_key,
        "locked_at": to_iso_utc(job.locked_at),
    }


def _as_float(value: object) -> float | None:
    return float(value) if value is not None else None
