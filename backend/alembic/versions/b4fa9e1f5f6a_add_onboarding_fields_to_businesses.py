"""add onboarding fields to businesses

Revision ID: b4fa9e1f5f6a
Revises: 31348c56a758
Create Date: 2026-07-05 16:17:59.796413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4fa9e1f5f6a'
down_revision: Union[str, Sequence[str], None] = '31348c56a758'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # server_default backfills existing rows (there is already one seeded
    # business in dev) so the NOT NULL constraint doesn't fail on ADD COLUMN.
    op.add_column('businesses', sa.Column('contact_email', sa.String(length=320), nullable=True))
    op.add_column('businesses', sa.Column('country', sa.String(length=100), nullable=True))
    op.add_column(
        'businesses',
        sa.Column('onboarding_status', sa.String(length=32), server_default='created', nullable=False),
    )
    op.add_column(
        'businesses',
        sa.Column(
            'whatsapp_connection_status',
            sa.String(length=24),
            server_default='not_connected',
            nullable=False,
        ),
    )
    op.add_column('businesses', sa.Column('website_url', sa.String(length=512), nullable=True))
    op.add_column('businesses', sa.Column('trial_ends_at', sa.DateTime(), nullable=True))
    # Note: this migration intentionally does not touch kb_entries/its HNSW
    # index — autogenerate flags it as "removed" only because Alembic can't
    # introspect pgvector's hnsw index options, not because of a real change.


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('businesses', 'trial_ends_at')
    op.drop_column('businesses', 'website_url')
    op.drop_column('businesses', 'whatsapp_connection_status')
    op.drop_column('businesses', 'onboarding_status')
    op.drop_column('businesses', 'country')
    op.drop_column('businesses', 'contact_email')
