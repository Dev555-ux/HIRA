"""set kb embedding dimension to 384 (bge-small)

Revision ID: 0f9137e8dd34
Revises: ea5a287d0681
Create Date: 2026-06-29 15:19:47.779006

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0f9137e8dd34'
down_revision: Union[str, Sequence[str], None] = 'ea5a287d0681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Switch kb_entries.embedding from vector(1536) to vector(384) for
    BAAI/bge-small-en-v1.5. Safe to cast directly while the column has no data."""
    op.execute("ALTER TABLE kb_entries ALTER COLUMN embedding TYPE vector(384)")


def downgrade() -> None:
    op.execute("ALTER TABLE kb_entries ALTER COLUMN embedding TYPE vector(1536)")
