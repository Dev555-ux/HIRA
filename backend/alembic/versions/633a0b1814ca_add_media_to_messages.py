"""add media to messages

Revision ID: 633a0b1814ca
Revises: 8e54f0810532
Create Date: 2026-08-18 20:34:18.430163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '633a0b1814ca'
down_revision: Union[str, Sequence[str], None] = '8e54f0810532'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'messages',
        sa.Column('media', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('messages', 'media')
