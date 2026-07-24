"""add unique index on businesses whatsapp_phone_number_id

Revision ID: 4f65b1c52f09
Revises: 9cb102b6f1b7
Create Date: 2026-07-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f65b1c52f09'
down_revision: Union[str, Sequence[str], None] = '9cb102b6f1b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Partial unique index: NULLs (businesses that haven't connected WhatsApp
    # yet) are excluded so they can coexist; only an actually-connected
    # phone_number_id must be unique across businesses (release-review fix —
    # the webhook routes inbound messages by this field, so two businesses
    # sharing one number would have the second connect silently steal the
    # first's traffic).
    op.create_index(
        'uq_businesses_whatsapp_phone_number_id',
        'businesses',
        ['whatsapp_phone_number_id'],
        unique=True,
        postgresql_where=sa.text('whatsapp_phone_number_id IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_businesses_whatsapp_phone_number_id', table_name='businesses')
