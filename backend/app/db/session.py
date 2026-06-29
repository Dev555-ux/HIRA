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
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
