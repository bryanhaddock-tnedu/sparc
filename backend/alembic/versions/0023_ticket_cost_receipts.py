"""Add Jira Team ticket-cost receipt support.

Revision ID: 0023_ticket_cost_receipts
Revises: 0022_sync_gaps
Create Date: 2026-08-31
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0023_ticket_cost_receipts"
down_revision: str | None = "0022_sync_gaps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("actual_entries", sa.Column("source_ticket_summary", sa.Text(), nullable=True))
    op.add_column("actual_entries", sa.Column("source_team", sa.String(length=160), nullable=True))
    op.add_column("actual_entries", sa.Column("source_story_points", sa.Numeric(precision=8, scale=2), nullable=True))
    op.create_table(
        "jira_team_estimation_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jira_team", sa.String(length=160), nullable=False),
        sa.Column("velocity_story_points", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("developer_capacity_hours", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("qa_percent_of_developer_hours", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("product_owner_percent_of_developer_hours", sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_team"),
    )


def downgrade() -> None:
    op.drop_table("jira_team_estimation_profiles")
    op.drop_column("actual_entries", "source_story_points")
    op.drop_column("actual_entries", "source_team")
    op.drop_column("actual_entries", "source_ticket_summary")
