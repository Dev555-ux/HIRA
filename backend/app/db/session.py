"""Database engine and session factory.

`engine` manages the connection pool to Postgres. `SessionLocal` produces
short-lived Session objects used per request/operation. `get_db` is a FastAPI
dependency that yields a session and always closes it afterwards.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
# PERF-1: expire_on_commit=False. The default (True) marks every attribute on
# every object in the session as stale after each commit, so merely reading
# an attribute afterwards (e.g. serializing a response) triggers an extra
# SELECT round-trip per object. Safe here because the one place this codebase
# actually needs a post-commit, server-generated value (created_at timestamps,
# etc.) it already calls db.refresh() explicitly — grep for `db.refresh(` — so
# nothing relies on the implicit re-fetch this disables.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
