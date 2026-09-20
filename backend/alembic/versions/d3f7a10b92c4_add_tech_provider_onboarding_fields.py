"""add tech provider onboarding fields and whatsapp_onboarding_attempts

Sprint 82 (Tech Provider foundation). Purely additive and backward
compatible: every new column is either nullable or carries a server_default,
and the one altered column is widened (NOT NULL -> NULL), never narrowed. No
existing row is read, rewritten, or migrated — guided-manual customers keep
working on exactly the values they already have, and `token_source` backfills
to 'manual' for all of them, which is what they are.

Revision ID: d3f7a10b92c4
Revises: a1c7d3f92b40
Create Date: 2026-09-19 10:12:38.114902

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d3f7a10b92c4"
down_revision: Union[str, Sequence[str], None] = "a1c7d3f92b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("businesses", sa.Column("meta_business_id", sa.String(length=64), nullable=True))
    op.add_column(
        "businesses",
        sa.Column(
            "whatsapp_registration_status",
            sa.String(length=24),
            server_default="not_registered",
            nullable=False,
        ),
    )

    # Embedded Signup customers have no per-business app secret at all —
    # Meta signs their webhooks with Stoneveil's. NULL becomes a meaningful
    # value for those rows; every existing row keeps its non-NULL secret.
    op.alter_column(
        "whatsapp_credentials",
        "app_secret_encrypted",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.add_column(
        "whatsapp_credentials",
        sa.Column("token_source", sa.String(length=24), server_default="manual", nullable=False),
    )
    op.add_column(
        "whatsapp_credentials", sa.Column("token_type", sa.String(length=32), nullable=True)
    )
    op.add_column("whatsapp_credentials", sa.Column("granted_scopes", sa.Text(), nullable=True))
    op.add_column(
        "whatsapp_credentials", sa.Column("token_expires_at", sa.DateTime(), nullable=True)
    )
    op.add_column(
        "whatsapp_credentials", sa.Column("two_factor_pin_encrypted", sa.Text(), nullable=True)
    )

    op.create_table(
        "whatsapp_onboarding_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("state", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        # UNIQUE is what actually enforces single-use of an onboarding state;
        # app/whatsapp/onboarding_attempts.py's consumed_at check is the
        # readable half of the same guarantee.
        sa.UniqueConstraint("state"),
    )
    op.create_index(
        op.f("ix_whatsapp_onboarding_attempts_business_id"),
        "whatsapp_onboarding_attempts",
        ["business_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_whatsapp_onboarding_attempts_business_id"),
        table_name="whatsapp_onboarding_attempts",
    )
    op.drop_table("whatsapp_onboarding_attempts")

    op.drop_column("whatsapp_credentials", "two_factor_pin_encrypted")
    op.drop_column("whatsapp_credentials", "token_expires_at")
    op.drop_column("whatsapp_credentials", "granted_scopes")
    op.drop_column("whatsapp_credentials", "token_type")
    op.drop_column("whatsapp_credentials", "token_source")
    # Restoring NOT NULL would fail if any Embedded Signup row exists, which
    # is correct: there is no non-lossy way back for a credential that never
    # had a per-business app secret to lose.
    op.alter_column(
        "whatsapp_credentials",
        "app_secret_encrypted",
        existing_type=sa.Text(),
        nullable=False,
    )

    op.drop_column("businesses", "whatsapp_registration_status")
    op.drop_column("businesses", "meta_business_id")
