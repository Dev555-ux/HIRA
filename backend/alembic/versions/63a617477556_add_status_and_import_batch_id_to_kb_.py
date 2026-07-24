"""add status and import_batch_id to kb_entries

Revision ID: 63a617477556
Revises: 7b7027673f4f
Create Date: 2026-07-22 16:45:57.758077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '63a617477556'
down_revision: Union[str, Sequence[str], None] = '7b7027673f4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('kb_entries', sa.Column('status', sa.String(length=20), server_default='published', nullable=False))
    op.add_column('kb_entries', sa.Column('import_batch_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_kb_entries_import_batch_id'), 'kb_entries', ['import_batch_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kb_entries_import_batch_id'), table_name='kb_entries')
    op.drop_column('kb_entries', 'import_batch_id')
    op.drop_column('kb_entries', 'status')
