"""add whatsapp display phone number to businesses

Revision ID: b65a38647967
Revises: 42923c8003d1
Create Date: 2026-07-26 00:02:44.228552

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b65a38647967'
down_revision: Union[str, Sequence[str], None] = '42923c8003d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Sprint 72: verify_whatsapp_credentials() already fetches this from
    # Meta (fields=display_phone_number) but previously discarded it — the
    # wizard's verify step referenced "your connected business number"
    # without ever being able to show what that number actually is.
    op.add_column(
        'businesses', sa.Column('whatsapp_display_phone_number', sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('businesses', 'whatsapp_display_phone_number')
