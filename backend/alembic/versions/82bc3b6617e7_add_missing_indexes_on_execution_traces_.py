"""add missing indexes on execution_traces business_id and conversation_id

Revision ID: 82bc3b6617e7
Revises: 1ff2626b9079
Create Date: 2026-08-06 17:52:06.810789

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "82bc3b6617e7"
down_revision: Union[str, Sequence[str], None] = "1ff2626b9079"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    High-priority audit fix (CI tests against real migrations): closes
    genuine, pre-existing drift the new alembic-built test schema surfaced
    — app/models.py's ExecutionTrace already declares business_id/
    conversation_id with index=True, but no earlier migration ever created
    them. Autogenerate also proposed dropping ix_kb_entries_embedding_hnsw
    — a known false positive (alembic's metadata comparison doesn't
    recognize pgvector's HNSW index type as matching the model's plain
    Index(), even though it's correct and already created by
    31348c56a758_add_hnsw_index_on_kb_embedding.py) — left out here
    deliberately, same as prior migrations' own unrelated-drift notes.
    """
    op.create_index(
        op.f("ix_execution_traces_business_id"), "execution_traces", ["business_id"], unique=False
    )
    op.create_index(
        op.f("ix_execution_traces_conversation_id"),
        "execution_traces",
        ["conversation_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_execution_traces_conversation_id"), table_name="execution_traces")
    op.drop_index(op.f("ix_execution_traces_business_id"), table_name="execution_traces")
