"""PR 3 (ADR-001 / IMP-001) — tests for the outbox worker & dispatcher.

Covers what PR 3 lands: claiming with FOR UPDATE SKIP LOCKED, handler dispatch,
the unknown-handler path, retry scheduling with backoff, the dead-letter
transition, zombie recovery, concurrent workers, batch processing, and graceful
shutdown. Handler-registry mechanics live in test_handlers.py.

Uses the shared `db_session` fixture for setup/assertions; the worker itself
runs against its own sessions built from a `sessionmaker` bound to the same test
engine (a real worker never shares the caller's session).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.jobs.handlers import (
    PermanentJobError,
    TransientJobError,
    clear_registry,
    register_handler,
)
from app.jobs.models import JobOutbox, JobStatus
from app.jobs.worker import OutboxWorker
from app.models import Business


@pytest.fixture
def worker_factory(db_session):
    """A sessionmaker bound to the same engine as the test's `db_session`, so a
    worker sees the rows the test creates (once committed) and vice versa."""
    return sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Keep the module-level handler registry isolated between tests."""
    clear_registry()
    yield
    clear_registry()


def _make_business(db) -> Business:
    business = Business(name="Outbox Clinic")
    db.add(business)
    db.flush()
    return business


def _make_job(db, business, *, task_name="do_work", payload=None, **kwargs) -> JobOutbox:
    job = JobOutbox(
        business_id=business.id,
        task_name=task_name,
        payload=payload if payload is not None else {},
        **kwargs,
    )
    db.add(job)
    db.flush()
    return job


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TestHandlerDispatch:
    def test_successful_handler_marks_job_completed(self, db_session, worker_factory):
        business = _make_business(db_session)
        job = _make_job(db_session, business, task_name="greet")
        db_session.commit()

        seen: list[uuid.UUID] = []

        def handler(db: Session, j: JobOutbox) -> None:
            seen.append(j.id)

        register_handler("greet", handler)
        worker = OutboxWorker(session_factory=worker_factory, worker_id="w1")

        assert worker.run_once() == 1
        assert seen == [job.id]

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.COMPLETED
        assert refreshed.locked_at is None and refreshed.locked_by is None

    def test_handler_writes_commit_atomically_with_completion(self, db_session, worker_factory):
        """A handler's business writes and the job's COMPLETED status are one
        transaction — the write is visible iff the job completed."""
        business = _make_business(db_session)
        job = _make_job(db_session, business, task_name="rename")
        db_session.commit()
        new_name = "Renamed By Handler"

        def handler(db: Session, j: JobOutbox) -> None:
            biz = db.get(Business, j.business_id)
            biz.name = new_name

        register_handler("rename", handler)
        OutboxWorker(session_factory=worker_factory).run_once()

        db_session.expire_all()
        assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED
        assert db_session.get(Business, business.id).name == new_name

    def test_failed_handler_writes_are_rolled_back(self, db_session, worker_factory):
        """A handler that writes then raises must leave no side effect behind."""
        business = _make_business(db_session)
        original = business.name
        _make_job(db_session, business, task_name="rename_then_fail", max_attempts=5)
        db_session.commit()

        def handler(db: Session, j: JobOutbox) -> None:
            db.get(Business, j.business_id).name = "Should Not Persist"
            raise TransientJobError("boom after write")

        register_handler("rename_then_fail", handler)
        OutboxWorker(session_factory=worker_factory).run_once()

        db_session.expire_all()
        assert db_session.get(Business, business.id).name == original


class TestUnknownHandler:
    def test_unknown_task_is_failed_not_crashed(self, db_session, worker_factory):
        business = _make_business(db_session)
        job = _make_job(db_session, business, task_name="no_such_task")
        db_session.commit()

        worker = OutboxWorker(session_factory=worker_factory)
        # Must not raise — an unknown task can never crash the worker.
        assert worker.run_once() == 1

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.FAILED
        assert "no_such_task" in refreshed.last_error
        assert refreshed.locked_at is None

    def test_unknown_task_does_not_block_the_rest_of_the_batch(self, db_session, worker_factory):
        business = _make_business(db_session)
        bad = _make_job(db_session, business, task_name="unknown")
        good = _make_job(db_session, business, task_name="known")
        db_session.commit()
        register_handler("known", lambda db, j: None)

        OutboxWorker(session_factory=worker_factory, batch_size=5).run_once()

        db_session.expire_all()
        assert db_session.get(JobOutbox, bad.id).status is JobStatus.FAILED
        assert db_session.get(JobOutbox, good.id).status is JobStatus.COMPLETED


class TestRetryScheduling:
    def test_transient_failure_reschedules_with_backoff(self, db_session, worker_factory):
        business = _make_business(db_session)
        job = _make_job(db_session, business, task_name="flaky", max_attempts=3)
        db_session.commit()

        def handler(db: Session, j: JobOutbox) -> None:
            raise TransientJobError("upstream 503")

        register_handler("flaky", handler)
        before = _utcnow()
        OutboxWorker(
            session_factory=worker_factory, backoff_base_seconds=2.0
        ).run_once()

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.PENDING  # back in the queue
        assert refreshed.attempts == 1
        assert "upstream 503" in refreshed.last_error
        assert refreshed.locked_by is None
        # First retry waits base**1 = 2s, so run_at is pushed into the future.
        assert refreshed.run_at > before + timedelta(seconds=1)

    def test_unexpected_exception_is_treated_as_transient(self, db_session, worker_factory):
        business = _make_business(db_session)
        job = _make_job(db_session, business, task_name="buggy", max_attempts=3)
        db_session.commit()

        def handler(db: Session, j: JobOutbox) -> None:
            raise RuntimeError("unexpected bug")

        register_handler("buggy", handler)
        OutboxWorker(session_factory=worker_factory).run_once()

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.PENDING
        assert refreshed.attempts == 1

    def test_backoff_grows_exponentially_and_is_capped(self):
        worker = OutboxWorker(
            session_factory=sessionmaker(),
            backoff_base_seconds=2.0,
            backoff_max_seconds=10.0,
        )
        assert worker._backoff_delay(1) == 2.0
        assert worker._backoff_delay(2) == 4.0
        assert worker._backoff_delay(3) == 8.0
        assert worker._backoff_delay(4) == 10.0  # 16 capped to 10
        assert worker._backoff_delay(10) == 10.0


class TestDeadLetter:
    def test_job_dead_letters_when_attempts_exhausted(self, db_session, worker_factory):
        business = _make_business(db_session)
        # One attempt away from the limit: this failure is the last one.
        job = _make_job(
            db_session, business, task_name="always_fails", max_attempts=3, attempts=2
        )
        db_session.commit()

        register_handler(
            "always_fails",
            lambda db, j: (_ for _ in ()).throw(TransientJobError("still broken")),
        )
        OutboxWorker(session_factory=worker_factory).run_once()

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.DEAD_LETTER
        assert refreshed.attempts == 3
        assert "still broken" in refreshed.last_error

    def test_permanent_error_fails_immediately_without_retry(self, db_session, worker_factory):
        business = _make_business(db_session)
        job = _make_job(db_session, business, task_name="bad_payload", max_attempts=5)
        db_session.commit()

        register_handler(
            "bad_payload",
            lambda db, j: (_ for _ in ()).throw(PermanentJobError("payload invalid")),
        )
        OutboxWorker(session_factory=worker_factory).run_once()

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.FAILED
        assert refreshed.attempts == 0  # never retried
        assert "payload invalid" in refreshed.last_error


class TestZombieRecovery:
    def test_stale_processing_job_returns_to_pending(self, db_session, worker_factory):
        business = _make_business(db_session)
        stale_lock = _utcnow() - timedelta(seconds=600)
        job = _make_job(
            db_session,
            business,
            task_name="orphaned",
            status=JobStatus.PROCESSING,
            locked_at=stale_lock,
            locked_by="dead-worker",
        )
        db_session.commit()

        recovered = OutboxWorker(
            session_factory=worker_factory, zombie_timeout_seconds=300
        ).recover_zombies()

        assert recovered == 1
        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.PENDING
        assert refreshed.locked_at is None and refreshed.locked_by is None

    def test_recently_locked_processing_job_is_not_recovered(self, db_session, worker_factory):
        business = _make_business(db_session)
        job = _make_job(
            db_session,
            business,
            task_name="in_progress",
            status=JobStatus.PROCESSING,
            locked_at=_utcnow() - timedelta(seconds=10),
            locked_by="live-worker",
        )
        db_session.commit()

        recovered = OutboxWorker(
            session_factory=worker_factory, zombie_timeout_seconds=300
        ).recover_zombies()

        assert recovered == 0
        db_session.expire_all()
        assert db_session.get(JobOutbox, job.id).status is JobStatus.PROCESSING


class TestConcurrentWorkersSkipLocked:
    def test_two_workers_never_claim_the_same_job(self, db_session, worker_factory):
        """FOR UPDATE SKIP LOCKED: while worker A holds a claim in an open
        transaction, worker B claims a *different* job rather than blocking or
        double-claiming."""
        business = _make_business(db_session)
        job_a = _make_job(db_session, business, task_name="t", run_at=_utcnow() - timedelta(minutes=1))
        job_b = _make_job(db_session, business, task_name="t", run_at=_utcnow() - timedelta(minutes=1))
        db_session.commit()

        worker_a = OutboxWorker(session_factory=worker_factory, batch_size=1, worker_id="A")
        worker_b = OutboxWorker(session_factory=worker_factory, batch_size=1, worker_id="B")

        db_a = worker_factory()
        db_b = worker_factory()
        try:
            # A selects+locks one row but does NOT commit — the lock is held.
            claimed_a = worker_a._select_and_lock(db_a, _utcnow())
            assert len(claimed_a) == 1

            # B, in a separate transaction, must skip A's locked row.
            claimed_b = worker_b._select_and_lock(db_b, _utcnow())
            assert len(claimed_b) == 1
            assert claimed_a[0].id != claimed_b[0].id
            assert {claimed_a[0].id, claimed_b[0].id} == {job_a.id, job_b.id}
        finally:
            db_a.rollback()
            db_b.rollback()
            db_a.close()
            db_b.close()

    def test_worker_skips_a_locked_row_and_takes_the_next(self, db_session, worker_factory):
        business = _make_business(db_session)
        locked = _make_job(db_session, business, task_name="known", run_at=_utcnow() - timedelta(minutes=1))
        free = _make_job(db_session, business, task_name="known", run_at=_utcnow() - timedelta(minutes=1))
        db_session.commit()
        register_handler("known", lambda db, j: None)

        holder = worker_factory()
        try:
            # Hold a lock on `locked` in an uncommitted transaction.
            held = OutboxWorker(session_factory=worker_factory, batch_size=1)._select_and_lock(
                holder, _utcnow()
            )
            held_id = held[0].id

            # A real worker cycle should process only the un-locked job.
            worker = OutboxWorker(session_factory=worker_factory, batch_size=5)
            processed = worker.run_once()
            assert processed == 1

            db_session.expire_all()
            other_id = free.id if held_id == locked.id else locked.id
            assert db_session.get(JobOutbox, other_id).status is JobStatus.COMPLETED
            # The still-locked job was skipped and remains claimable.
            assert db_session.get(JobOutbox, held_id).status is JobStatus.PENDING
        finally:
            holder.rollback()
            holder.close()


class TestBatchProcessing:
    def test_claims_up_to_batch_size_in_one_cycle(self, db_session, worker_factory):
        business = _make_business(db_session)
        ids = [_make_job(db_session, business, task_name="k").id for _ in range(5)]
        db_session.commit()
        register_handler("k", lambda db, j: None)

        processed = OutboxWorker(session_factory=worker_factory, batch_size=3).run_once()

        assert processed == 3
        db_session.expire_all()
        completed = [
            db_session.get(JobOutbox, i).status is JobStatus.COMPLETED for i in ids
        ]
        assert completed.count(True) == 3  # exactly the batch, not more

    def test_future_dated_jobs_are_not_claimed(self, db_session, worker_factory):
        business = _make_business(db_session)
        due = _make_job(db_session, business, task_name="k", run_at=_utcnow() - timedelta(minutes=1))
        later = _make_job(
            db_session, business, task_name="k", run_at=_utcnow() + timedelta(hours=1)
        )
        db_session.commit()
        register_handler("k", lambda db, j: None)

        processed = OutboxWorker(session_factory=worker_factory, batch_size=10).run_once()

        assert processed == 1
        db_session.expire_all()
        assert db_session.get(JobOutbox, due.id).status is JobStatus.COMPLETED
        assert db_session.get(JobOutbox, later.id).status is JobStatus.PENDING


class TestGracefulShutdown:
    def test_finishes_current_job_and_releases_the_rest(self, db_session, worker_factory):
        """A shutdown requested from inside a handler lets that job finish, then
        stops — remaining claimed jobs are released back to PENDING, not left
        stranded in PROCESSING."""
        business = _make_business(db_session)
        first = _make_job(db_session, business, task_name="shutter", run_at=_utcnow() - timedelta(minutes=1))
        second = _make_job(db_session, business, task_name="shutter", run_at=_utcnow() - timedelta(minutes=1))
        db_session.commit()

        worker = OutboxWorker(session_factory=worker_factory, batch_size=2)
        finished: list[uuid.UUID] = []

        def handler(db: Session, j: JobOutbox) -> None:
            finished.append(j.id)
            worker.request_shutdown()  # ask to stop mid-batch

        register_handler("shutter", handler)
        worker.run_once()

        # Exactly one job was processed to completion...
        assert len(finished) == 1
        db_session.expire_all()
        statuses = {db_session.get(JobOutbox, first.id).status, db_session.get(JobOutbox, second.id).status}
        assert JobStatus.COMPLETED in statuses
        # ...and the other is back to PENDING (released), never left PROCESSING.
        assert JobStatus.PENDING in statuses
        for job_id in (first.id, second.id):
            assert db_session.get(JobOutbox, job_id).status is not JobStatus.PROCESSING

    def test_run_loop_exits_when_shutdown_requested(self, db_session, worker_factory):
        """run() must return (not spin) once shutdown is set, even with an empty
        queue."""
        worker = OutboxWorker(session_factory=worker_factory, poll_interval=0.01)
        worker.request_shutdown()
        # If run() ignored the flag this would loop forever; a return is the test.
        worker.run()
