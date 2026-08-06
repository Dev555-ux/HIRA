"""Outbox worker & dispatcher (Sprint 64 — ADR-001 / IMP-001, PR 3).

A standalone, synchronous process that drains `job_outbox`. It runs in its own
OS process (see `scripts/run_worker.py`), never inside the API process, and it
knows *nothing* about business logic — it only:

1. **claims** due PENDING jobs with ``FOR UPDATE SKIP LOCKED`` (so N workers
   share the queue without ever fighting over the same row),
2. **dispatches** each to its registered handler (see `app/jobs/handlers.py`),
3. **records the outcome** — COMPLETED, a backed-off retry, FAILED, or
   DEAD_LETTER — and moves on.

All business behaviour lives in handlers. Adding background work never touches
this file.

Transaction model (the important part):

* **Claim** is its own short transaction: select a batch FOR UPDATE SKIP LOCKED,
  flip it to PROCESSING with a lock stamp, commit. The rows are now durably
  owned by this worker.
* **Each job is then processed in its own fresh transaction.** The handler
  writes through that session and, on success, the worker marks the job
  COMPLETED and commits — so the handler's business writes and the terminal
  status are one atomic unit. On failure the handler's partial writes are rolled
  back before the status change is recorded, so a failed job never leaks half a
  side effect.
* If the worker dies between claim and finish, the job is left PROCESSING and is
  recovered by the **zombie sweep** (returned to PENDING after
  `outbox_zombie_timeout_seconds`).

This module is synchronous on purpose: the whole codebase uses sync SQLAlchemy /
psycopg, and ``SKIP LOCKED`` gives us horizontal scaling by simply running more
processes — no async runtime or new dependency required.

Nothing here runs while `use_transactional_outbox` is False, because no code
path enqueues jobs yet (the webhook dual-write lands in PR 4); a worker started
now simply finds an empty queue and idles.
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import threading
import traceback
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.session import SessionLocal
from app.jobs.handlers import PermanentJobError, get_handler
from app.jobs.models import JobOutbox, JobStatus

logger = logging.getLogger(__name__)

# locked_by is String(128); a host:pid[:short-uuid] tag fits comfortably and is
# enough to tell two workers apart in logs and in the locked_by column.
_LOCKED_BY_MAX = 128
# last_error is Text, but a runaway traceback in the DB helps no one — keep the
# tail (the actual exception line is at the end of a traceback).
_LAST_ERROR_MAX = 4000


def _utcnow() -> datetime:
    """Timezone-aware UTC now. The job_outbox timestamp columns are
    ``TIMESTAMP WITH TIME ZONE`` (unlike the naive-UTC columns elsewhere in this
    schema), so the worker works in aware UTC throughout for run_at / locked_at
    comparisons and backoff arithmetic."""
    return datetime.now(timezone.utc)


def _default_worker_id() -> str:
    tag = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"
    return tag[:_LOCKED_BY_MAX]


class OutboxWorker:
    """Claims and dispatches outbox jobs. Construct one per process and call
    :meth:`run`; tests drive a single cycle via :meth:`run_once`.

    All tuning defaults come from `settings` but are overridable for tests.
    """

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] = SessionLocal,
        worker_id: str | None = None,
        batch_size: int | None = None,
        poll_interval: float | None = None,
        zombie_timeout_seconds: int | None = None,
        backoff_base_seconds: float | None = None,
        backoff_max_seconds: float | None = None,
        queue_name: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.worker_id = worker_id or _default_worker_id()
        self.batch_size = batch_size if batch_size is not None else settings.outbox_worker_batch_size
        self.poll_interval = (
            poll_interval if poll_interval is not None else settings.outbox_worker_poll_interval
        )
        self.zombie_timeout_seconds = (
            zombie_timeout_seconds
            if zombie_timeout_seconds is not None
            else settings.outbox_zombie_timeout_seconds
        )
        self.backoff_base_seconds = (
            backoff_base_seconds
            if backoff_base_seconds is not None
            else settings.outbox_backoff_base_seconds
        )
        self.backoff_max_seconds = (
            backoff_max_seconds
            if backoff_max_seconds is not None
            else settings.outbox_backoff_max_seconds
        )
        # None => all queues; a value scopes this worker to one queue_name.
        self.queue_name = queue_name
        self._shutdown = threading.Event()

    # ----------------------------------------------------------------- lifecycle

    def run(self) -> None:
        """Poll-process-sleep until shutdown is requested, then exit cleanly.

        Installs SIGTERM/SIGINT handlers that request a graceful shutdown: the
        loop stops claiming new work, lets the in-flight job finish, and
        releases any already-claimed-but-unstarted jobs back to PENDING so they
        aren't stranded in PROCESSING.
        """
        self._install_signal_handlers()
        logger.info(
            "Outbox worker starting worker_id=%s batch_size=%s poll_interval=%ss "
            "zombie_timeout=%ss queue=%s",
            self.worker_id,
            self.batch_size,
            self.poll_interval,
            self.zombie_timeout_seconds,
            self.queue_name or "*",
        )
        try:
            while not self._shutdown.is_set():
                processed = self.run_once()
                if processed == 0:
                    # Nothing to do — sleep, but wake immediately on shutdown.
                    self._shutdown.wait(self.poll_interval)
        finally:
            logger.info("Outbox worker stopped worker_id=%s", self.worker_id)

    def request_shutdown(self) -> None:
        """Ask the worker to stop after the current job. Idempotent; safe to call
        from a signal handler or another thread."""
        self._shutdown.set()

    def _install_signal_handlers(self) -> None:
        def _handle(signum, _frame):
            logger.info(
                "Outbox worker received signal=%s, finishing current job then exiting "
                "worker_id=%s",
                signal.Signals(signum).name,
                self.worker_id,
            )
            self.request_shutdown()

        # Only valid in the main thread; ignore if we're embedded elsewhere.
        try:
            signal.signal(signal.SIGTERM, _handle)
            signal.signal(signal.SIGINT, _handle)
        except ValueError:
            logger.debug("Signal handlers not installed (not in main thread)")

    # ------------------------------------------------------------- one poll cycle

    def run_once(self) -> int:
        """Run a single poll cycle: recover zombies, claim a batch, process it.

        Returns the number of jobs processed (dispatched to an outcome) this
        cycle — 0 means the queue had no due work, which the caller uses to
        decide whether to sleep.
        """
        self.recover_zombies()
        self.recover_stale_sending_messages()

        claimed_ids = self._claim_batch()
        if not claimed_ids:
            return 0

        processed = 0
        for index, job_id in enumerate(claimed_ids):
            if self._shutdown.is_set():
                # Graceful shutdown mid-batch: don't start new jobs. Release the
                # remainder we claimed but haven't touched, so they return to
                # PENDING instead of lingering as PROCESSING zombies.
                self._release_unstarted(claimed_ids[index:])
                break
            self._process_job(job_id)
            processed += 1
        return processed

    # --------------------------------------------------------------------- claim

    def _claim_batch(self) -> list[uuid.UUID]:
        """Atomically claim up to `batch_size` due PENDING jobs.

        ``FOR UPDATE SKIP LOCKED`` is what makes concurrent workers safe: each
        worker's SELECT locks the rows it reads and skips any already locked by
        another worker's open transaction, so two workers never claim the same
        job and neither blocks the other.
        """
        with self._session() as db:
            jobs = self._select_and_lock(db, _utcnow())
            claimed_ids = [job.id for job in jobs]
            db.commit()

        for job_id in claimed_ids:
            logger.info(
                "Outbox job claimed job_id=%s worker_id=%s", job_id, self.worker_id
            )
        return claimed_ids

    def _select_and_lock(self, db: Session, now: datetime) -> list[JobOutbox]:
        """SELECT ... FOR UPDATE SKIP LOCKED the next due batch on `db` and flip
        it to PROCESSING with this worker's lock stamp. The rows stay locked
        until `db` is committed or rolled back — so this is the single point that
        makes concurrent claiming safe, and the seam tests use to hold a lock
        open across two sessions.

        Due-ness is evaluated with the *database* clock (``func.now()``), not the
        passed-in Python `now`: run_at is written by the DB clock (server default
        / retry scheduling), and comparing DB-generated timestamps against a
        possibly-skewed app clock would otherwise leave freshly enqueued jobs
        briefly unclaimable. `now` is used only for this worker's lock stamp.
        """
        stmt = (
            select(JobOutbox)
            .where(JobOutbox.status == JobStatus.PENDING, JobOutbox.run_at <= func.now())
            .order_by(JobOutbox.run_at)
            .limit(self.batch_size)
            .with_for_update(skip_locked=True)
        )
        if self.queue_name is not None:
            stmt = stmt.where(JobOutbox.queue_name == self.queue_name)

        jobs = list(db.scalars(stmt).all())
        for job in jobs:
            job.status = JobStatus.PROCESSING
            job.locked_at = now
            job.locked_by = self.worker_id
        db.flush()
        return jobs

    # ------------------------------------------------------------------- dispatch

    def _process_job(self, job_id: uuid.UUID) -> None:
        """Dispatch one claimed job to its handler and record the outcome.

        Runs in a fresh transaction. On success the handler's writes and the
        COMPLETED status commit together; on failure the handler's partial writes
        are rolled back before the retry/FAILED status is recorded.
        """
        with self._session() as db:
            job = db.get(JobOutbox, job_id)
            if job is None or job.status is not JobStatus.PROCESSING:
                # Lost the row to a zombie sweep + re-claim, or it vanished
                # (business deleted -> FK cascade). Nothing to do.
                return

            handler = get_handler(job.task_name)
            if handler is None:
                # Unknown task must never crash the worker: record and FAIL it,
                # then keep going with the rest of the batch.
                self._mark_failed(
                    db, job, f"No handler registered for task {job.task_name!r}"
                )
                db.commit()
                logger.warning(
                    "Outbox job has no handler job_id=%s task=%s -> FAILED worker_id=%s",
                    job.id,
                    job.task_name,
                    self.worker_id,
                )
                return

            try:
                handler(db, job)
            except PermanentJobError as exc:
                db.rollback()
                job = db.get(JobOutbox, job_id)
                if job is not None:
                    self._mark_failed(db, job, _format_error(exc))
                    db.commit()
                    logger.warning(
                        "Outbox job permanently failed job_id=%s task=%s -> FAILED "
                        "worker_id=%s error=%s",
                        job_id,
                        job.task_name,
                        self.worker_id,
                        exc,
                    )
            except Exception as exc:  # noqa: BLE001 — worker must survive any handler error
                db.rollback()
                job = db.get(JobOutbox, job_id)
                if job is not None:
                    self._record_transient_failure(db, job, exc)
                    db.commit()
            else:
                self._mark_completed(db, job)
                db.commit()
                logger.info(
                    "Outbox job completed job_id=%s task=%s attempts=%s worker_id=%s",
                    job.id,
                    job.task_name,
                    job.attempts,
                    self.worker_id,
                )

    # ------------------------------------------------------------------ outcomes

    def _mark_completed(self, db: Session, job: JobOutbox) -> None:
        job.status = JobStatus.COMPLETED
        job.locked_at = None
        job.locked_by = None
        job.updated_at = _utcnow()

    def _mark_failed(self, db: Session, job: JobOutbox, error: str) -> None:
        """Terminal, non-retryable failure (unknown task or PermanentJobError)."""
        job.status = JobStatus.FAILED
        job.last_error = error[:_LAST_ERROR_MAX]
        job.locked_at = None
        job.locked_by = None
        job.updated_at = _utcnow()

    def _record_transient_failure(self, db: Session, job: JobOutbox, exc: Exception) -> None:
        """Increment attempts and either schedule a backed-off retry or, once
        `max_attempts` is exhausted, move the job to the dead-letter queue."""
        job.attempts += 1
        job.last_error = _format_error(exc)[:_LAST_ERROR_MAX]
        job.locked_at = None
        job.locked_by = None
        job.updated_at = _utcnow()

        if job.attempts >= job.max_attempts:
            job.status = JobStatus.DEAD_LETTER
            logger.error(
                "Outbox job dead-lettered job_id=%s task=%s attempts=%s/%s worker_id=%s "
                "error=%s",
                job.id,
                job.task_name,
                job.attempts,
                job.max_attempts,
                self.worker_id,
                exc,
            )
        else:
            delay = self._backoff_delay(job.attempts)
            job.status = JobStatus.PENDING
            job.run_at = _utcnow() + timedelta(seconds=delay)
            logger.warning(
                "Outbox job retry scheduled job_id=%s task=%s attempt=%s/%s "
                "next_run_in=%.1fs worker_id=%s error=%s",
                job.id,
                job.task_name,
                job.attempts,
                job.max_attempts,
                delay,
                self.worker_id,
                exc,
            )

    def _backoff_delay(self, attempts: int) -> float:
        """Exponential backoff: base**attempts, capped. attempts is the count
        *after* this failure, so the first retry waits base**1."""
        raw = self.backoff_base_seconds**attempts
        return min(raw, self.backoff_max_seconds)

    # -------------------------------------------------------------------- zombies

    def recover_zombies(self) -> int:
        """Return jobs stuck in PROCESSING past the zombie timeout to PENDING.

        A job is a zombie when the worker that claimed it died before recording
        an outcome, so its lock is never released. After
        `outbox_zombie_timeout_seconds` we reclaim it: clear the lock and set it
        back to PENDING so any worker can pick it up again. attempts is left
        untouched — a crash isn't the *job's* fault — which is why a genuinely
        poisonous job is ultimately bounded by max_attempts through the normal
        transient-failure path, not by the zombie sweep.
        """
        cutoff = _utcnow() - timedelta(seconds=self.zombie_timeout_seconds)
        with self._session() as db:
            result = db.execute(
                update(JobOutbox)
                .where(
                    JobOutbox.status == JobStatus.PROCESSING,
                    JobOutbox.locked_at < cutoff,
                )
                .values(
                    status=JobStatus.PENDING,
                    locked_at=None,
                    locked_by=None,
                    updated_at=_utcnow(),
                )
                .returning(JobOutbox.id)
            )
            recovered_ids = [row[0] for row in result.all()]
            db.commit()

        for job_id in recovered_ids:
            logger.warning(
                "Outbox zombie recovered job_id=%s -> PENDING (locked past %ss) worker_id=%s",
                job_id,
                self.zombie_timeout_seconds,
                self.worker_id,
            )
        return len(recovered_ids)

    def recover_stale_sending_messages(self) -> int:
        """Critical audit fix #2, Part D: sweep for Messages stuck in
        "sending" past their timeout — the same shape as recover_zombies()
        above (same reason to run it every poll cycle: this worker process
        is already the one long-running, continuously-scheduled loop in
        this codebase — see scripts/run_worker.py), applied to a different
        table's own "claimed but never resolved" state. All the actual
        logic (the query, the terminal-state transition, the tool_call
        escalation) lives in app/services/replies.py, right next to the
        approve_and_send() state machine it recovers — this just supplies
        the periodic trigger, via this worker's own session lifecycle.

        Imported locally, not at module level: app/jobs/__init__.py imports
        this module eagerly (`from app.jobs.worker import OutboxWorker`),
        and app/models.py imports app.jobs.models at module scope too — a
        top-level import here of app.services.replies (which pulls in the
        whole app.ai.* chain, which imports app.models for its own ORM
        classes) closes a real cycle back through app.models while it's
        still mid-definition. Deferring the import to call time breaks that
        cycle without changing app/jobs/__init__.py's or app/models.py's own
        existing import shape.
        """
        from app.services.replies import recover_stale_sending_messages

        with self._session() as db:
            return recover_stale_sending_messages(db)

    # ------------------------------------------------------------------ shutdown

    def _release_unstarted(self, job_ids: list[uuid.UUID]) -> None:
        """On graceful shutdown, hand back jobs we claimed but never started so
        they don't sit in PROCESSING waiting for the zombie timeout."""
        if not job_ids:
            return
        with self._session() as db:
            db.execute(
                update(JobOutbox)
                .where(
                    JobOutbox.id.in_(job_ids),
                    JobOutbox.status == JobStatus.PROCESSING,
                    JobOutbox.locked_by == self.worker_id,
                )
                .values(
                    status=JobStatus.PENDING,
                    locked_at=None,
                    locked_by=None,
                    updated_at=_utcnow(),
                )
            )
            db.commit()
        logger.info(
            "Outbox worker released %s unstarted job(s) on shutdown worker_id=%s",
            len(job_ids),
            self.worker_id,
        )

    # -------------------------------------------------------------------- helpers

    def _session(self) -> _SessionContext:
        return _SessionContext(self._session_factory)


class _SessionContext:
    """Small context manager: yields a Session, rolls back and closes on any
    exception, always closes on exit. Keeps the worker body free of try/finally
    boilerplate around every short transaction."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory
        self._session: Session | None = None

    def __enter__(self) -> Session:
        self._session = self._factory()
        return self._session

    def __exit__(self, exc_type, exc, tb) -> None:
        assert self._session is not None
        try:
            if exc_type is not None:
                self._session.rollback()
        finally:
            self._session.close()


def _format_error(exc: BaseException) -> str:
    """Compact, structured error string for last_error: the exception type and
    message, plus a short traceback tail for debugging."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return f"{type(exc).__name__}: {exc}\n{tb}"
