"""add assigned_to to escalations

Revision ID: dd02cae501ba
Revises: 7b7027673f4f
Create Date: 2026-07-22 17:19:26.114987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'dd02cae501ba'
down_revision: Union[str, Sequence[str], None] = '7b7027673f4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('escalations', sa.Column('assigned_to', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'escalations_assigned_to_fkey',
        'escalations',
        'users',
        ['assigned_to'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('escalations_assigned_to_fkey', 'escalations', type_='foreignkey')
    op.drop_column('escalations', 'assigned_to')
