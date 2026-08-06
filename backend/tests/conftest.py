"""Shared test fixtures.

High-priority audit fix (CI tests against real migrations, not
Base.metadata.create_all()): the schema is now built by running the real
Alembic migration chain (`alembic upgrade head`) against TEST_DATABASE_URL,
once per test session — not by asking SQLAlchemy to derive CREATE TABLE
statements from the current app/models.py. A model that drifts from its
migration (a column/index declared on a model with nothing in
alembic/versions/ to create it, or a migration that's broken/out of order)
now surfaces as a real failure here, the same way it would in production's
own `alembic upgrade head` (Dockerfile CMD) — instead of silently passing
locally, where create_all() would happily build tables straight from
whatever the model currently says, migration history notwithstanding.

Per-session, not per-test: replaying the full migration chain (~19 files)
for every single test would make the suite dramatically slower for no
extra safety, since the schema itself is identical test to test — only the
data in it needs to reset. Each test instead gets a clean slate via
TRUNCATE (see `db_session` below), which is what actually varies between
tests.

A real Postgres is required (our models use pgvector / JSONB), so tests run
against TEST_DATABASE_URL (a dedicated test database) — CREATE EXTENSION
IF NOT EXISTS vector is handled by the first real migration itself
(ea5a287d0681_create_initial_schema.py), the same as it is in production,
so nothing here needs to do it separately anymore.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import limiter
from app.db.base import Base
import app.models  # noqa: F401  — register models on Base.metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:hira_dev_pw@localhost:5432/hira_test",
)

_BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _migrated_schema() -> None:
    """Run `alembic upgrade head` against TEST_DATABASE_URL once, before any
    test in the session. ALEMBIC_DATABASE_URL (see alembic/env.py) is what
    points this same, unmodified migration chain at the test database
    instead of settings.database_url (a different database locally — see
    .env's DATABASE_URL vs. this module's TEST_DATABASE_URL default).

    Session-scoped and autouse: every test that touches the database goes
    through `db_session` below, which itself depends on this fixture, so
    this always runs first regardless of which test happens to run first.
    """
    os.environ["ALEMBIC_DATABASE_URL"] = TEST_DATABASE_URL
    try:
        command.upgrade(Config(str(_BACKEND_DIR / "alembic.ini")), "head")
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """The rate limiter (app/core/rate_limit.py) is a module-level singleton
    with in-memory storage — without this, tests that repeatedly hit the
    same rate-limited endpoint (e.g. many onboarding tests posting to
    POST /business) accumulate hits across the whole test run and start
    failing with 429s that have nothing to do with what they're testing."""
    limiter.limiter.storage.reset()
    yield
    limiter.limiter.storage.reset()


@pytest.fixture
def db_session(_migrated_schema):
    engine = create_engine(TEST_DATABASE_URL)
    table_names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    if table_names:
        with engine.begin() as conn:
            conn.execute(text(f"TRUNCATE TABLE {table_names} CASCADE"))

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session: Session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
