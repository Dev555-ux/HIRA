"""High-priority audit fix — tests for the migration-based test schema
itself: that `alembic upgrade head` (not Base.metadata.create_all()) is what
builds the schema tests run against, that it matches app/models.py exactly
(drift detection), and that the underlying mechanics (fresh init, repeat
init, a broken/missing target) behave the way CI needs them to.

See tests/conftest.py's `_migrated_schema` fixture (what every other test
file relies on implicitly) and alembic/env.py's ALEMBIC_DATABASE_URL
override (what points that same, unmodified migration chain at the test
database instead of the dev one).
"""

import os
import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, inspect, text

from app.db.base import Base
from tests.conftest import TEST_DATABASE_URL

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = str(BACKEND_DIR / "alembic.ini")

# The one alembic/SQLAlchemy-comparison limitation this suite knows about and
# deliberately excludes, not a real drift item: alembic's schema comparison
# doesn't recognize pgvector's HNSW index type as matching app/models.py's
# plain Index() declaration, so it always proposes "removing" an index that
# is, in fact, present and correct (created by
# alembic/versions/31348c56a758_add_hnsw_index_on_kb_embedding.py). Anything
# else compare_metadata reports is real drift and must fail this suite.
_KNOWN_COMPARISON_LIMITATIONS = {("index", "ix_kb_entries_embedding_hnsw")}


def _include_object(object_, name, type_, reflected, compare_to) -> bool:
    return (type_, name) not in _KNOWN_COMPARISON_LIMITATIONS


# --- 1/2. The test DB is built through Alembic, and migrations reach head --


def test_test_database_has_an_alembic_version_table(db_session):
    """Only `alembic upgrade head` creates this table — Base.metadata.
    create_all() has no concept of it, since it isn't part of any ORM
    model. Its presence is direct proof the schema came from the real
    migration chain, not from ORM metadata."""
    tables = inspect(db_session.get_bind()).get_table_names()
    assert "alembic_version" in tables


def test_test_database_is_at_the_real_migration_head(db_session):
    current = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    heads = ScriptDirectory.from_config(Config(ALEMBIC_INI)).get_heads()
    assert len(heads) == 1, f"expected a single migration head, found {heads}"
    assert current == heads[0]


# --- 3. Schema matches expected models (drift detection, Part C) -----------


def test_migrated_schema_matches_orm_metadata_exactly(db_session):
    """The core safety net this fix exists to add: if a model changes
    without a corresponding migration (or a migration doesn't match what
    the model actually declares), this fails here — in CI, on every PR —
    instead of only in production the first time that code path runs.

    Uses alembic.autogenerate.compare_metadata — the documented, built-in
    API for exactly this comparison — rather than any custom schema-diff
    tooling (Part C's explicit preference).
    """
    conn = db_session.connection()
    context = MigrationContext.configure(conn, opts={"include_object": _include_object})
    diffs = compare_metadata(context, Base.metadata)
    assert diffs == [], (
        "app/models.py and the Alembic migration chain have drifted — every model "
        "change needs a matching migration (or vice versa):\n" + "\n".join(str(d) for d in diffs)
    )


# --- 4. Existing tests still run unchanged ----------------------------------
#
# Not a single test here — the claim is that every other test file in this
# suite, unmodified, still passes against the alembic-built schema. That's
# verified by running the full suite, not by one test asserting it (see this
# change's own test-results writeup); duplicating that here would just be a
# slower, narrower copy of the same thing pytest's own exit code already says.


# --- 5. Fresh database initialization ---------------------------------------


def test_alembic_upgrade_head_initializes_a_completely_fresh_database():
    """Starting from nothing — no tables, no alembic_version — `alembic
    upgrade head` must build the entire schema successfully, the same as
    it does against a brand-new production database on first deploy
    (Dockerfile's CMD runs this exact command before uvicorn starts)."""
    admin_engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    fresh_db_name = f"hira_test_fresh_{uuid.uuid4().hex[:8]}"
    base_url = TEST_DATABASE_URL.rsplit("/", 1)[0]
    fresh_url = f"{base_url}/{fresh_db_name}"

    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{fresh_db_name}"'))
    try:
        os.environ["ALEMBIC_DATABASE_URL"] = fresh_url
        try:
            command.upgrade(Config(ALEMBIC_INI), "head")
        finally:
            os.environ.pop("ALEMBIC_DATABASE_URL", None)

        fresh_engine = create_engine(fresh_url)
        try:
            tables = inspect(fresh_engine).get_table_names()
            assert "alembic_version" in tables
            # A representative sample, not every table — proof the full
            # chain ran end to end, not just its first migration.
            assert {"businesses", "messages", "job_outbox", "execution_traces"} <= set(tables)
        finally:
            fresh_engine.dispose()
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{fresh_db_name}"'))
        admin_engine.dispose()


# --- 6. Repeat initialization ------------------------------------------------


def test_alembic_upgrade_head_is_idempotent(db_session):
    """Running `upgrade head` again against an already-migrated database
    (what happens on every deploy after the first, and what this suite's
    own session-scoped fixture would do if it ever ran twice) is a safe
    no-op — alembic checks the current revision in alembic_version and does
    nothing further once already at head."""
    os.environ["ALEMBIC_DATABASE_URL"] = TEST_DATABASE_URL
    try:
        command.upgrade(Config(ALEMBIC_INI), "head")  # must not raise
        command.upgrade(Config(ALEMBIC_INI), "head")  # nor the second time
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)

    current = db_session.execute(text("SELECT version_num FROM alembic_version")).scalar()
    heads = ScriptDirectory.from_config(Config(ALEMBIC_INI)).get_heads()
    assert current == heads[0]
    # Exactly one row — a repeat upgrade never appends a second bookkeeping
    # row for the same (single-head) chain.
    count = db_session.execute(text("SELECT count(*) FROM alembic_version")).scalar()
    assert count == 1


# --- 7. Migration failure surfaces clearly -----------------------------------


def test_upgrading_to_an_unknown_revision_raises_clearly():
    """A broken/missing migration target must fail loudly — CommandError
    with a message naming the problem — never silently no-op or leave the
    caller to discover it only once something downstream breaks."""
    os.environ["ALEMBIC_DATABASE_URL"] = TEST_DATABASE_URL
    try:
        with pytest.raises(CommandError, match="Can't locate revision"):
            command.upgrade(Config(ALEMBIC_INI), "not_a_real_revision")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
