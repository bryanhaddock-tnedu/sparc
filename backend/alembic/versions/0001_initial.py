"""Initial SPARK schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("jira_space_key", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=True)
    op.create_unique_constraint(op.f("uq_products_jira_space_key"), "products", ["jira_space_key"])

    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("staff_id", sa.String(length=60), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=120), nullable=False),
        sa.Column("team", sa.String(length=120), nullable=False),
        sa.Column("bill_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("employment_type", sa.String(length=80), nullable=False),
        sa.Column("contracting_company", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("staff_id"),
    )
    op.create_index(op.f("ix_team_members_name"), "team_members", ["name"], unique=False)

    op.create_table(
        "buckets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "fiscal_months",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("calendar_year", sa.Integer(), nullable=False),
        sa.Column("calendar_month", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=16), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fiscal_year", "sequence", name="uq_fiscal_month_year_sequence"),
    )
    op.create_index(op.f("ix_fiscal_months_fiscal_year"), "fiscal_months", ["fiscal_year"], unique=False)

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "forecast_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("team_member_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_month_id", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["fiscal_month_id"], ["fiscal_months.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            name="uq_forecast_product_member_bucket_month",
        ),
    )

    op.create_table(
        "jira_user_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jira_account_id", sa.String(length=160), nullable=False),
        sa.Column("jira_display_name", sa.String(length=160), nullable=False),
        sa.Column("jira_email", sa.String(length=160), nullable=True),
        sa.Column("team_member_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_account_id"),
    )

    op.create_table(
        "jira_product_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jira_project_key", sa.String(length=80), nullable=False),
        sa.Column("jira_project_name", sa.String(length=160), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_project_key"),
    )

    op.create_table(
        "actual_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sync_run_id", sa.Integer(), nullable=True),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("team_member_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_month_id", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("source_issue_id", sa.String(length=120), nullable=True),
        sa.Column("source_ticket_key", sa.String(length=80), nullable=True),
        sa.Column("source_worklog_id", sa.String(length=120), nullable=True),
        sa.Column("source_account_id", sa.String(length=160), nullable=True),
        sa.Column("source_project_key", sa.String(length=80), nullable=True),
        sa.Column("source_payload_hash", sa.String(length=128), nullable=True),
        sa.Column("is_team_member_time", sa.Boolean(), nullable=False),
        sa.Column("worked_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["fiscal_month_id"], ["fiscal_months.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["sync_run_id"], ["sync_runs.id"]),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            "source_ticket_key",
            "source_worklog_id",
            name="uq_actual_source_worklog",
        ),
    )


def downgrade() -> None:
    op.drop_table("actual_entries")
    op.drop_table("jira_product_mappings")
    op.drop_table("jira_user_mappings")
    op.drop_table("forecast_entries")
    op.drop_table("sync_runs")
    op.drop_index(op.f("ix_fiscal_months_fiscal_year"), table_name="fiscal_months")
    op.drop_table("fiscal_months")
    op.drop_table("buckets")
    op.drop_index(op.f("ix_team_members_name"), table_name="team_members")
    op.drop_table("team_members")
    op.drop_constraint(op.f("uq_products_jira_space_key"), "products", type_="unique")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_table("products")
