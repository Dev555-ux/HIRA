"""Alembic migration environment.

Wires Alembic to our app: it reads the database URL from our settings (.env)
and uses Base.metadata (populated by importing app.models) as the source of
truth when autogenerating migrations.
"""

import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

import app.models  # noqa: F401  — import registers all models on Base.metadata
from alembic import context
from app.core.config import settings
from app.db.base import Base

config = context.config
# High-priority audit fix (CI tests against real migrations, not
# Base.metadata.create_all()): ALEMBIC_DATABASE_URL, set only by
# tests/conftest.py's session-scoped schema fixture, lets the test suite
# point this same, unmodified migration chain at TEST_DATABASE_URL instead
# of the dev/production database settings.database_url would otherwise
# resolve to — those are two different databases locally (see .env vs.
# TEST_DATABASE_URL's own default), so without this override, running
# migrations from a test process would touch the wrong one. Unset in every
# other context (a developer's own `alembic upgrade head`/`alembic
# revision --autogenerate`, and production's Dockerfile CMD), so this is a
# no-op everywhere except that one test fixture.
config.set_main_option(
    "sqlalchemy.url", os.environ.get("ALEMBIC_DATABASE_URL", settings.database_url)
)

if config.config_file_name is not None:
    # disable_existing_loggers=False (fileConfig's own default is True):
    # alembic.ini's [loggers] section only lists root/sqlalchemy/alembic,
    # so the default would silently disable every other already-registered
    # logger — every app.* logger, and pytest's own — for the rest of the
    # process. Harmless for the CLI (the process exits right after, e.g.
    # Dockerfile's `alembic upgrade head && uvicorn ...`), but a real bug
    # once this runs in-process from tests/conftest.py's session-scoped
    # fixture (High-priority audit fix: CI tests against real migrations):
    # it broke every test asserting on caplog output for the rest of the
    # session, since app.jobs.queue etc. had gone silently disabled.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
