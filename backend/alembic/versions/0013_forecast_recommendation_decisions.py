"""Audit forecast recommendation decisions.

Revision ID: 0013_forecast_recommendation_decisions
Revises: 0012_roadmap_item_source_category
Create Date: 2026-07-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0013_forecast_recommendation_decisions"
down_revision: str | None = "0012_roadmap_item_source_category"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "forecast_recommendation_decisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("bucket_id", sa.Integer(), sa.ForeignKey("buckets.id"), nullable=False),
        sa.Column("recommendation", sa.String(length=40), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("forecast_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("roadmap_actual_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("suggested_delta_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("suggested_forecast_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("target_team_member_id", sa.Integer(), sa.ForeignKey("team_members.id"), nullable=True),
        sa.Column("target_month_sequence", sa.Integer(), nullable=True),
        sa.Column("applied_forecast_entry_id", sa.Integer(), sa.ForeignKey("forecast_entries.id"), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_forecast_recommendation_decisions_fiscal_year", "forecast_recommendation_decisions", ["fiscal_year"])


def downgrade() -> None:
    op.drop_index("ix_forecast_recommendation_decisions_fiscal_year", table_name="forecast_recommendation_decisions")
    op.drop_table("forecast_recommendation_decisions")
