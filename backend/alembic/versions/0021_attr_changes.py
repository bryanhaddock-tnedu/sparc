"""Add attribution correction audit history.

Revision ID: 0021_attr_changes
Revises: 0020_data_integrity
Create Date: 2026-07-15
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0021_attr_changes"
down_revision: str | None = "0020_data_integrity"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attribution_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.String(length=60), nullable=False),
        sa.Column("source_key", sa.String(length=160), nullable=False),
        sa.Column("from_value", sa.Text(), nullable=True),
        sa.Column("to_value", sa.Text(), nullable=True),
        sa.Column("affected_actual_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_hours", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("affected_cost", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("changed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("changed_by_display_name", sa.String(length=160), nullable=False),
        sa.Column("changed_by_email", sa.String(length=320), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["changed_by_user_id"], ["app_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attribution_changes_change_type", "attribution_changes", ["change_type"])
    op.create_index("ix_attribution_changes_source_key", "attribution_changes", ["source_key"])
    op.create_index("ix_attribution_changes_created_at", "attribution_changes", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_attribution_changes_created_at", table_name="attribution_changes")
    op.drop_index("ix_attribution_changes_source_key", table_name="attribution_changes")
    op.drop_index("ix_attribution_changes_change_type", table_name="attribution_changes")
    op.drop_table("attribution_changes")
