"""add conversation summary fields

Revision ID: b526e4d40196
Revises: c5b02a421ba8
Create Date: 2026-07-09 21:29:03.628452

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b526e4d40196"
down_revision: Union[str, Sequence[str], None] = "c5b02a421ba8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("conversations", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("summary_message_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "summary_message_count")
    op.drop_column("conversations", "summary")
