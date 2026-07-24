"""merge sprint 69 heads (whatsapp, knowledge safety, escalation queue)

Revision ID: 42923c8003d1
Revises: 4f65b1c52f09, 63a617477556, dd02cae501ba
Create Date: 2026-07-24 22:30:15.245282

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '42923c8003d1'
down_revision: Union[str, Sequence[str], None] = ('4f65b1c52f09', '63a617477556', 'dd02cae501ba')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
