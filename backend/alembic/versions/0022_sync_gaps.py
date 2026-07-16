"""Add Jira worklog exclusion diagnostics.

Revision ID: 0022_sync_gaps
Revises: 0021_attr_changes
Create Date: 2026-07-16
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0022_sync_gaps"
down_revision: str | None = "0021_attr_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jira_worklog_exclusions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=False),
        sa.Column("source_issue_id", sa.String(length=160), nullable=True),
        sa.Column("source_worklog_id", sa.String(length=160), nullable=False),
        sa.Column("ticket_key", sa.String(length=80), nullable=False),
        sa.Column("ticket_summary", sa.Text(), nullable=True),
        sa.Column("jira_project_key", sa.String(length=80), nullable=False),
        sa.Column("jira_project_name", sa.String(length=160), nullable=True),
        sa.Column("jira_account_id", sa.String(length=160), nullable=True),
        sa.Column("jira_display_name", sa.String(length=160), nullable=True),
        sa.Column("worked_on", sa.Date(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("work_type_value", sa.String(length=160), nullable=True),
        sa.Column("invalid_work_type", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unmapped_user", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unmapped_product", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["sync_run_id"], ["sync_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jira_worklog_exclusions_sync_run_id", "jira_worklog_exclusions", ["sync_run_id"])
    op.create_index("ix_jira_worklog_exclusions_ticket_key", "jira_worklog_exclusions", ["ticket_key"])


def downgrade() -> None:
    op.drop_index("ix_jira_worklog_exclusions_ticket_key", table_name="jira_worklog_exclusions")
    op.drop_index("ix_jira_worklog_exclusions_sync_run_id", table_name="jira_worklog_exclusions")
    op.drop_table("jira_worklog_exclusions")
