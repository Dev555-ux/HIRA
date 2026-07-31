"""add job_outbox table

Revision ID: c8f2e91a4b3d
Revises: 71b629d0085b
Create Date: 2026-07-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c8f2e91a4b3d"
down_revision: Union[str, Sequence[str], None] = "71b629d0085b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# The job_status ENUM is created explicitly below and referenced with
# create_type=False on the column, so op.create_table does not try to CREATE
# TYPE a second time (the classic Alembic enum double-create failure).
job_status = postgresql.ENUM(
    "pending",
    "processing",
    "completed",
    "failed",
    "dead_letter",
    name="job_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    job_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "job_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("queue_name", sa.String(length=64), server_default="default", nullable=False),
        sa.Column("task_name", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", job_status, server_default="pending", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=128), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=256), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_job_outbox_idempotency_key"),
    )

    op.create_index(
        "ix_job_outbox_fetch",
        "job_outbox",
        ["queue_name", "status", "run_at"],
        postgresql_where=sa.text("status IN ('pending', 'processing')"),
    )
    op.create_index("ix_job_outbox_business_status", "job_outbox", ["business_id", "status"])
    op.create_index(
        "ix_job_outbox_zombie",
        "job_outbox",
        ["status", "locked_at"],
        postgresql_where=sa.text("status = 'processing'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_job_outbox_zombie", table_name="job_outbox")
    op.drop_index("ix_job_outbox_business_status", table_name="job_outbox")
    op.drop_index("ix_job_outbox_fetch", table_name="job_outbox")
    op.drop_table("job_outbox")
    job_status.drop(op.get_bind(), checkfirst=True)
