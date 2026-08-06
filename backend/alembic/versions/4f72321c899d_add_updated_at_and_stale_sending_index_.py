"""add updated_at and stale-sending index to messages

Revision ID: 4f72321c899d
Revises: c8f2e91a4b3d
Create Date: 2026-08-06 12:57:10.220397

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4f72321c899d"
down_revision: Union[str, Sequence[str], None] = "c8f2e91a4b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Autogenerate also picked up unrelated pre-existing model/DB drift
    (execution_traces' index reflection, the pgvector HNSW index on
    kb_entries) that has nothing to do with this change — left out here
    deliberately; not this migration's concern to fix.
    """
    op.add_column(
        "messages",
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index(
        "ix_messages_sending_updated",
        "messages",
        ["status", "updated_at"],
        unique=False,
        postgresql_where=sa.text("status = 'sending'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "ix_messages_sending_updated",
        table_name="messages",
        postgresql_where=sa.text("status = 'sending'"),
    )
    op.drop_column("messages", "updated_at")
