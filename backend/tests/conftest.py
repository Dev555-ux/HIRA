"""Shared test fixtures.

`db_session` provides a clean Postgres-backed session for each test: it ensures
the pgvector extension exists, creates all tables, yields a session, then drops
everything. A real Postgres is required (our models use pgvector / JSONB), so
tests run against TEST_DATABASE_URL (a dedicated test database).
"""

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
import app.models  # noqa: F401  — register models on Base.metadata

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:hira_dev_pw@localhost:5432/hira_test",
)


@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL)
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session: Session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()
