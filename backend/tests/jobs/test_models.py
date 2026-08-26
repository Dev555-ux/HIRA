"""PR 1 (ADR-001 / IMP-001) — unit tests for the transactional outbox schema.

Covers the four things PR 1 actually lands: the JobStatus ENUM, the JobOutbox
ORM model (columns / server defaults), its indexes, and the Alembic migration
that creates the table. No enqueue, worker, or webhook behaviour exists yet, so
there is nothing runtime to exercise here — those arrive in later PRs.

The ORM tests use the shared `db_session` fixture (schema built via the real
Alembic migration chain — see tests/conftest.py). The migration test runs the
real migration's upgrade()/downgrade() against Postgres inside a rolled-back
transaction, so it exercises the actual DDL without polluting the shared test
database.
"""

import importlib.util
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.jobs.models import JobOutbox, JobStatus
from app.models import Business
from tests.conftest import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = BACKEND_DIR / "alembic" / "versions" / "c8f2e91a4b3d_add_job_outbox_table.py"

EXPECTED_STATUS_VALUES = ["pending", "processing", "completed", "failed", "dead_letter"]


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("_job_outbox_migration", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_business(db) -> Business:
    business = Business(name="Outbox Clinic")
    db.add(business)
    db.flush()
    return business


class TestJobStatusEnum:
    def test_values_and_order_match_the_ddl(self):
        assert [s.value for s in JobStatus] == EXPECTED_STATUS_VALUES

    def test_is_a_str_enum(self):
        # values_callable serialises the .value, and str-subclassing lets call
        # sites compare against the raw wire strings.
        assert JobStatus.PENDING == "pending"
        assert JobStatus.DEAD_LETTER.value == "dead_letter"


class TestJobOutboxModel:
    def test_defaults_are_applied_on_insert(self, db_session):
        business = _make_business(db_session)
        job = JobOutbox(
            business_id=business.id,
            task_name="generate_ai_reply",
            payload={"message_id": "abc"},
        )
        db_session.add(job)
        db_session.flush()
        db_session.refresh(job)

        assert isinstance(job.id, uuid.UUID)
        assert job.status is JobStatus.PENDING
        assert job.queue_name == "default"
        assert job.attempts == 0
        assert job.max_attempts == 5
        assert job.run_at is not None
        assert job.created_at is not None
        assert job.updated_at is not None
        assert job.locked_at is None
        assert job.locked_by is None
        assert job.last_error is None
        assert job.idempotency_key is None

    def test_payload_round_trips_as_jsonb(self, db_session):
        business = _make_business(db_session)
        payload = {"message_id": "m1", "nested": {"n": 1}, "list": [1, 2, 3]}
        job = JobOutbox(business_id=business.id, task_name="t", payload=payload)
        db_session.add(job)
        db_session.flush()
        db_session.expire(job)
        assert job.payload == payload

    def test_status_accepts_every_enum_member(self, db_session):
        business = _make_business(db_session)
        for status in JobStatus:
            job = JobOutbox(
                business_id=business.id,
                task_name="t",
                payload={},
                status=status,
            )
            db_session.add(job)
        db_session.flush()

    def test_idempotency_key_is_unique(self, db_session):
        business = _make_business(db_session)
        db_session.add(
            JobOutbox(business_id=business.id, task_name="t", payload={}, idempotency_key="dup")
        )
        db_session.flush()
        db_session.add(
            JobOutbox(business_id=business.id, task_name="t", payload={}, idempotency_key="dup")
        )
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestJobOutboxIndexes:
    def test_expected_indexes_exist(self, db_session):
        index_names = {
            ix["name"] for ix in inspect(db_session.get_bind()).get_indexes("job_outbox")
        }
        assert {
            "ix_job_outbox_fetch",
            "ix_job_outbox_business_status",
            "ix_job_outbox_zombie",
        } <= index_names

    def test_partial_indexes_carry_their_where_clause(self, db_session):
        rows = db_session.execute(
            text("SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'job_outbox'")
        ).all()
        defs = {name: indexdef for name, indexdef in rows}
        assert "WHERE" in defs["ix_job_outbox_fetch"]
        assert (
            "processing" in defs["ix_job_outbox_zombie"] and "WHERE" in defs["ix_job_outbox_zombie"]
        )
        # The tenant-scoped index is deliberately full, not partial.
        assert "WHERE" not in defs["ix_job_outbox_business_status"]


class TestJobOutboxMigration:
    def test_revision_chains_onto_the_real_head(self):
        module = _load_migration_module()
        assert module.revision == "c8f2e91a4b3d"
        assert module.down_revision == "71b629d0085b"

    def test_migration_leaves_a_single_head(self):
        # Pinned to the current chain tip, not literally c8f2e91a4b3d (this
        # PR's own migration) — bumped whenever a later migration is
        # appended (most recently a1c7d3f92b40, Sprint 73: ctwa_clid on
        # conversations + whatsapp_dataset_id on businesses, for the
        # Click-to-WhatsApp LeadSubmitted conversion event), same
        # maintenance this assertion has always implied.
        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        script = ScriptDirectory.from_config(cfg)
        assert script.get_heads() == ["a1c7d3f92b40"]

    def test_upgrade_then_downgrade_round_trips(self):
        module = _load_migration_module()
        engine = create_engine(TEST_DATABASE_URL)
        conn = engine.connect()
        trans = conn.begin()
        try:
            # High-priority audit fix (CI tests against real migrations):
            # the shared test database is now built by the *real* migration
            # chain once per session (tests/conftest.py), so job_outbox
            # (and businesses) already exist here — unlike before, when
            # this ran against a database Base.metadata.create_all() never
            # touched. Drop them within this same rolled-back transaction
            # first, so module.upgrade() below still starts from the clean
            # "table doesn't exist yet" state it's actually testing —
            # trans.rollback() at the end restores the session-wide schema
            # exactly as it was, unaffected by any of this.
            conn.execute(text("DROP TABLE IF EXISTS job_outbox CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS job_status CASCADE"))
            # job_outbox.business_id is an FK onto businesses(id); the migration
            # assumes that table already exists in the real chain.
            Base.metadata.tables["businesses"].create(conn, checkfirst=True)
            ctx = MigrationContext.configure(conn)

            with Operations.context(ctx):
                module.upgrade()

            assert _enum_values(conn, "job_status") == EXPECTED_STATUS_VALUES
            assert _table_exists(conn, "job_outbox")
            assert {
                "ix_job_outbox_fetch",
                "ix_job_outbox_business_status",
                "ix_job_outbox_zombie",
            } <= _index_names(conn, "job_outbox")

            with Operations.context(ctx):
                module.downgrade()

            assert not _table_exists(conn, "job_outbox")
            assert _enum_values(conn, "job_status") == []
        finally:
            trans.rollback()
            conn.close()
            engine.dispose()


def _table_exists(conn, name: str) -> bool:
    return conn.execute(text("SELECT to_regclass(:n)"), {"n": name}).scalar() is not None


def _enum_values(conn, name: str) -> list[str]:
    return (
        conn.execute(
            text(
                "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON e.enumtypid = t.oid "
                "WHERE t.typname = :n ORDER BY e.enumsortorder"
            ),
            {"n": name},
        )
        .scalars()
        .all()
    )


def _index_names(conn, table: str) -> set[str]:
    rows = (
        conn.execute(text("SELECT indexname FROM pg_indexes WHERE tablename = :t"), {"t": table})
        .scalars()
        .all()
    )
    return set(rows)
