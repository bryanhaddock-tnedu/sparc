"""Add estimation foundation tables.

Revision ID: 0005_estimation_foundation
Revises: 0004_product_jira_spaces
Create Date: 2026-05-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_estimation_foundation"
down_revision: str | None = "0004_product_jira_spaces"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "estimation_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("method_version", sa.String(length=80), nullable=False),
        sa.Column("monthly_capacity_hours", sa.Numeric(8, 2), nullable=False),
        sa.Column("actual_completeness_threshold", sa.Numeric(5, 4), nullable=False),
        sa.Column("stale_ticket_window_days", sa.Integer(), nullable=False),
        sa.Column("forecast_future_months", sa.Boolean(), nullable=False),
        sa.Column("future_month_average_window", sa.Integer(), nullable=False),
        sa.Column("excluded_statuses", sa.Text(), nullable=True),
        sa.Column("low_activity_statuses", sa.Text(), nullable=True),
        sa.Column("excluded_jira_project_keys", sa.Text(), nullable=True),
        sa.Column("project_pause_dates", sa.Text(), nullable=True),
        sa.Column("work_type_field_priority", sa.Text(), nullable=True),
        sa.Column("story_point_weighting_enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "estimation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("method_version", sa.String(length=80), nullable=False),
        sa.Column("rules_snapshot", sa.Text(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("source_jira_updated_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_jira_updated_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("imported_issue_count", sa.Integer(), nullable=False),
        sa.Column("estimated_entry_count", sa.Integer(), nullable=False),
        sa.Column("warning_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["estimation_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_estimation_runs_fiscal_year"), "estimation_runs", ["fiscal_year"], unique=False)

    op.create_table(
        "estimated_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estimation_run_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("team_member_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_month_id", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("method_version", sa.String(length=80), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("source_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["estimation_run_id"], ["estimation_runs.id"]),
        sa.ForeignKeyConstraint(["fiscal_month_id"], ["fiscal_months.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "estimation_run_id",
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            name="uq_estimate_run_product_member_bucket_month",
        ),
    )

    op.create_table(
        "estimated_issue_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("estimation_run_id", sa.Integer(), nullable=False),
        sa.Column("team_member_id", sa.Integer(), nullable=False),
        sa.Column("issue_id", sa.String(length=120), nullable=False),
        sa.Column("issue_key", sa.String(length=80), nullable=False),
        sa.Column("issue_summary", sa.Text(), nullable=True),
        sa.Column("jira_project_key", sa.String(length=80), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("bucket_id", sa.Integer(), nullable=True),
        sa.Column("fiscal_month_id", sa.Integer(), nullable=True),
        sa.Column("allocated_hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("issue_status", sa.String(length=120), nullable=True),
        sa.Column("status_category", sa.String(length=80), nullable=True),
        sa.Column("issue_type", sa.String(length=120), nullable=True),
        sa.Column("story_points", sa.Numeric(8, 2), nullable=True),
        sa.Column("issue_logged_hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at_from_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at_from_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at_from_jira", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active_window_start", sa.Date(), nullable=True),
        sa.Column("active_window_end", sa.Date(), nullable=True),
        sa.Column("included", sa.Boolean(), nullable=False),
        sa.Column("inclusion_reason", sa.Text(), nullable=True),
        sa.Column("exclusion_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["estimation_run_id"], ["estimation_runs.id"]),
        sa.ForeignKeyConstraint(["fiscal_month_id"], ["fiscal_months.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("estimated_issue_allocations")
    op.drop_table("estimated_entries")
    op.drop_index(op.f("ix_estimation_runs_fiscal_year"), table_name="estimation_runs")
    op.drop_table("estimation_runs")
    op.drop_table("estimation_profiles")
