"""add ctwa_clid to conversations and whatsapp_dataset_id to businesses

Revision ID: a1c7d3f92b40
Revises: 82bc3b6617e7
Create Date: 2026-08-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c7d3f92b40'
down_revision: Union[str, Sequence[str], None] = '82bc3b6617e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'conversations',
        sa.Column('ctwa_clid', sa.String(length=512), nullable=True),
    )
    op.add_column(
        'businesses',
        sa.Column('whatsapp_dataset_id', sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('businesses', 'whatsapp_dataset_id')
    op.drop_column('conversations', 'ctwa_clid')
