"""add hnsw index on kb embedding

Revision ID: 31348c56a758
Revises: 0f9137e8dd34
Create Date: 2026-06-29 16:28:19.508902

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '31348c56a758'
down_revision: Union[str, Sequence[str], None] = '0f9137e8dd34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add an HNSW index for fast cosine-similarity search on KB embeddings."""
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kb_entries_embedding_hnsw "
        "ON kb_entries USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_kb_entries_embedding_hnsw")
