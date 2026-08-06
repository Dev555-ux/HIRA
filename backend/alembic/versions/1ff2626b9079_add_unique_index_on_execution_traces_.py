"""add unique index on execution_traces trigger_message_id

Revision ID: 1ff2626b9079
Revises: 4f72321c899d
Create Date: 2026-08-06 17:08:35.015485

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1ff2626b9079"
down_revision: Union[str, Sequence[str], None] = "4f72321c899d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Autogenerate also picked up unrelated pre-existing model/DB drift
    (execution_traces.business_id/conversation_id index reflection, the
    pgvector HNSW index on kb_entries) that predates this change and has
    nothing to do with it — left out deliberately, same as the previous
    migration (4f72321c899d).
    """
    op.create_index(
        "uq_execution_traces_trigger_message_id",
        "execution_traces",
        ["trigger_message_id"],
        unique=True,
        postgresql_where=sa.text("trigger_message_id IS NOT NULL"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_execution_traces_trigger_message_id",
        table_name="execution_traces",
        postgresql_where=sa.text("trigger_message_id IS NOT NULL"),
    )
