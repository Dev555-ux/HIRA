"""SQLAlchemy declarative base.

Every ORM model inherits from `Base`. Alembic reads `Base.metadata` to know
the full set of tables when generating migrations.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
