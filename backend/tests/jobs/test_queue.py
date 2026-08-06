"""PR 2 (ADR-001 / IMP-001) — unit tests for the outbox enqueue service.

Covers what PR 2 lands: `OutboxService` / `enqueue_job` create a single PENDING
`job_outbox` row inside the caller's transaction, without committing; validate
their inputs; support strongly typed (Pydantic) payloads; and dedupe on
`idempotency_key`. No worker, polling, or dispatch behaviour exists yet, so
there is nothing to exercise beyond creation.

Uses the shared `db_session` fixture (a real Postgres session, schema built via
the real Alembic migration chain — see tests/conftest.py), matching
tests/jobs/test_models.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel
from sqlalchemy import create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.jobs import OutboxService, OutboxValidationError, enqueue_job
from app.jobs.models import JobOutbox, JobStatus
from app.models import Business
from tests.conftest import TEST_DATABASE_URL


def _make_business(db) -> Business:
    business = Business(name="Outbox Clinic")
    db.add(business)
    db.flush()
    return business


def _count_jobs(db) -> int:
    return db.scalar(select(func.count()).select_from(JobOutbox))


class SampleReplyPayload(BaseModel):
    """A strongly typed payload, exercising the Pydantic-model code path."""

    message_id: uuid.UUID
    conversation_id: uuid.UUID
    attempt_after: datetime


class TestEnqueueCreation:
    def test_creates_a_pending_job_with_expected_defaults(self, db_session):
        business = _make_business(db_session)

        job = enqueue_job(
            db_session,
            business_id=business.id,
            task_name="generate_ai_reply",
            payload={"message_id": "abc"},
        )

        assert job is not None
        assert isinstance(job.id, uuid.UUID)
        assert job.business_id == business.id
        assert job.task_name == "generate_ai_reply"
        assert job.payload == {"message_id": "abc"}
        assert job.status is JobStatus.PENDING
        assert job.queue_name == "default"
        assert job.attempts == 0
        assert job.max_attempts == 5
        assert job.idempotency_key is None

    def test_server_generated_timestamps_are_populated(self, db_session):
        business = _make_business(db_session)
        job = enqueue_job(
            db_session, business_id=business.id, task_name="t", payload={}
        )
        # created_at / updated_at / run_at come from the DB clock (func.now()),
        # the same source every other table in this schema uses.
        assert job.created_at is not None
        assert job.updated_at is not None
        assert job.run_at is not None

    def test_queue_name_override_is_honoured(self, db_session):
        business = _make_business(db_session)
        job = enqueue_job(
            db_session,
            business_id=business.id,
            task_name="t",
            payload={},
            queue_name="whatsapp",
        )
        assert job.queue_name == "whatsapp"

    def test_max_attempts_override_is_honoured(self, db_session):
        business = _make_business(db_session)
        job = enqueue_job(
            db_session,
            business_id=business.id,
            task_name="t",
            payload={},
            max_attempts=10,
        )
        assert job.max_attempts == 10

    def test_run_at_override_is_stored(self, db_session):
        business = _make_business(db_session)
        # Naive-but-UTC, matching this schema's timestamp convention (DEC-032).
        future = (datetime.now(timezone.utc) + timedelta(minutes=5)).replace(tzinfo=None)
        job = enqueue_job(
            db_session,
            business_id=business.id,
            task_name="t",
            payload={},
            run_at=future,
        )
        db_session.refresh(job)
        assert job.run_at.replace(tzinfo=None) == future

    def test_service_class_and_function_are_equivalent(self, db_session):
        business = _make_business(db_session)
        via_class = OutboxService(db_session).enqueue(
            business_id=business.id, task_name="t", payload={"k": 1}
        )
        via_fn = enqueue_job(
            db_session, business_id=business.id, task_name="t", payload={"k": 2}
        )
        assert via_class is not None and via_fn is not None
        assert via_class.id != via_fn.id


class TestPayloadHandling:
    def test_dict_payload_round_trips_as_jsonb(self, db_session):
        business = _make_business(db_session)
        payload = {"message_id": "m1", "nested": {"n": 1}, "list": [1, 2, 3]}
        job = enqueue_job(
            db_session, business_id=business.id, task_name="t", payload=payload
        )
        db_session.expire(job)
        assert job.payload == payload

    def test_pydantic_payload_is_serialised_to_json_safe_dict(self, db_session):
        business = _make_business(db_session)
        payload = SampleReplyPayload(
            message_id=uuid.uuid4(),
            conversation_id=uuid.uuid4(),
            attempt_after=datetime(2026, 7, 31, 12, 0, 0),
        )

        job = enqueue_job(
            db_session, business_id=business.id, task_name="generate_ai_reply", payload=payload
        )
        db_session.expire(job)

        # UUID/datetime became JSON-safe strings; the row survives a JSONB round trip.
        assert job.payload["message_id"] == str(payload.message_id)
        assert job.payload["conversation_id"] == str(payload.conversation_id)
        assert isinstance(job.payload["attempt_after"], str)

    def test_empty_dict_payload_is_allowed(self, db_session):
        business = _make_business(db_session)
        job = enqueue_job(db_session, business_id=business.id, task_name="t", payload={})
        assert job is not None
        assert job.payload == {}


class TestValidation:
    def test_blank_task_name_is_rejected(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError, match="task_name"):
            enqueue_job(db_session, business_id=business.id, task_name="   ", payload={})

    def test_overlong_task_name_is_rejected(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError, match="task_name"):
            enqueue_job(
                db_session, business_id=business.id, task_name="x" * 129, payload={}
            )

    def test_blank_queue_name_is_rejected(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError, match="queue_name"):
            enqueue_job(
                db_session, business_id=business.id, task_name="t", payload={}, queue_name=""
            )

    def test_blank_idempotency_key_is_rejected(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError, match="idempotency_key"):
            enqueue_job(
                db_session,
                business_id=business.id,
                task_name="t",
                payload={},
                idempotency_key="  ",
            )

    def test_max_attempts_below_one_is_rejected(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError, match="max_attempts"):
            enqueue_job(
                db_session, business_id=business.id, task_name="t", payload={}, max_attempts=0
            )

    def test_non_mapping_payload_is_rejected(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError, match="payload"):
            enqueue_job(db_session, business_id=business.id, task_name="t", payload=[1, 2, 3])

    def test_non_json_serialisable_payload_is_rejected(self, db_session):
        business = _make_business(db_session)
        # A raw uuid value in a plain dict isn't JSON-safe — the caller should
        # pass a Pydantic model (auto-serialised) or JSON-safe values instead.
        with pytest.raises(OutboxValidationError, match="JSON"):
            enqueue_job(
                db_session,
                business_id=business.id,
                task_name="t",
                payload={"id": uuid.uuid4()},
            )

    def test_non_uuid_business_id_is_rejected(self, db_session):
        with pytest.raises(OutboxValidationError, match="business_id"):
            enqueue_job(db_session, business_id="not-a-uuid", task_name="t", payload={})

    def test_validation_failure_creates_no_row(self, db_session):
        business = _make_business(db_session)
        with pytest.raises(OutboxValidationError):
            enqueue_job(db_session, business_id=business.id, task_name="", payload={})
        assert _count_jobs(db_session) == 0


class TestTransactionalBehaviour:
    def test_enqueue_does_not_commit_independently(self, db_session):
        """The whole point of the outbox: the job lives in the caller's
        transaction. Rolling that transaction back must discard the job."""
        business = _make_business(db_session)
        enqueue_job(db_session, business_id=business.id, task_name="t", payload={})
        assert _count_jobs(db_session) == 1  # visible within the open transaction

        db_session.rollback()

        assert _count_jobs(db_session) == 0  # gone — it was never committed

    def test_job_persists_after_caller_commits(self, db_session):
        business = _make_business(db_session)
        job = enqueue_job(db_session, business_id=business.id, task_name="t", payload={})
        job_id = job.id
        db_session.commit()

        # A fresh session only sees it because the caller's commit made it durable.
        engine = create_engine(TEST_DATABASE_URL)
        other: Session = sessionmaker(bind=engine)()
        try:
            assert other.get(JobOutbox, job_id) is not None
        finally:
            other.close()
            engine.dispose()

    def test_multiple_jobs_share_one_transaction_atomically(self, db_session):
        business = _make_business(db_session)
        enqueue_job(db_session, business_id=business.id, task_name="a", payload={})
        enqueue_job(db_session, business_id=business.id, task_name="b", payload={})
        assert _count_jobs(db_session) == 2
        db_session.rollback()
        assert _count_jobs(db_session) == 0


class TestIdempotency:
    def test_duplicate_idempotency_key_is_a_noop_returning_none(self, db_session):
        business = _make_business(db_session)
        first = enqueue_job(
            db_session,
            business_id=business.id,
            task_name="t",
            payload={"v": 1},
            idempotency_key="whatsapp:msg-1",
        )
        second = enqueue_job(
            db_session,
            business_id=business.id,
            task_name="t",
            payload={"v": 2},
            idempotency_key="whatsapp:msg-1",
        )

        assert first is not None
        assert second is None
        assert _count_jobs(db_session) == 1

    def test_distinct_idempotency_keys_create_distinct_jobs(self, db_session):
        business = _make_business(db_session)
        a = enqueue_job(
            db_session, business_id=business.id, task_name="t", payload={}, idempotency_key="k1"
        )
        b = enqueue_job(
            db_session, business_id=business.id, task_name="t", payload={}, idempotency_key="k2"
        )
        assert a is not None and b is not None and a.id != b.id
        assert _count_jobs(db_session) == 2

    def test_dedup_leaves_the_callers_transaction_usable(self, db_session):
        """A deduplicated enqueue must not poison the session: the caller can
        keep working and enqueue further jobs in the same transaction."""
        business = _make_business(db_session)
        enqueue_job(
            db_session, business_id=business.id, task_name="t", payload={}, idempotency_key="dup"
        )
        assert (
            enqueue_job(
                db_session,
                business_id=business.id,
                task_name="t",
                payload={},
                idempotency_key="dup",
            )
            is None
        )
        # Session is still healthy — a subsequent, different enqueue succeeds.
        follow_up = enqueue_job(
            db_session, business_id=business.id, task_name="t2", payload={}, idempotency_key="new"
        )
        assert follow_up is not None
        db_session.commit()
        assert _count_jobs(db_session) == 2


class TestIntegrityErrorDoesNotPoisonCallerTransaction:
    def test_fk_violation_is_savepoint_scoped(self, db_session):
        """An integrity error that is NOT an idempotency conflict (here an
        unknown business_id FK) is surfaced to the caller, but the SAVEPOINT
        keeps the caller's outer transaction alive — a subsequent valid
        enqueue in the same session still commits."""
        real_business = _make_business(db_session)
        db_session.commit()  # commit the business so the good enqueue below has a valid FK

        with pytest.raises(IntegrityError):
            enqueue_job(
                db_session, business_id=uuid.uuid4(), task_name="t", payload={}
            )

        # The outer transaction survived the failed INSERT: a good enqueue works.
        good = enqueue_job(
            db_session, business_id=real_business.id, task_name="t", payload={}
        )
        assert good is not None
        db_session.commit()
        assert _count_jobs(db_session) == 1


class TestLogging:
    def test_successful_enqueue_is_logged(self, db_session, caplog):
        business = _make_business(db_session)
        with caplog.at_level("INFO", logger="app.jobs.queue"):
            job = enqueue_job(db_session, business_id=business.id, task_name="t", payload={})
        assert any(str(job.id) in record.message for record in caplog.records)

    def test_dedup_is_logged(self, db_session, caplog):
        business = _make_business(db_session)
        enqueue_job(
            db_session, business_id=business.id, task_name="t", payload={}, idempotency_key="k"
        )
        with caplog.at_level("INFO", logger="app.jobs.queue"):
            enqueue_job(
                db_session, business_id=business.id, task_name="t", payload={}, idempotency_key="k"
            )
        assert any("deduplicated" in record.message for record in caplog.records)
