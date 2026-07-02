"""Add roadmap team and forecast allocations.

Revision ID: 0015_roadmap_forecast_plan
Revises: 0014_roadmap_deliv_links
Create Date: 2026-07-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0015_roadmap_forecast_plan"
down_revision: str | None = "0014_roadmap_deliv_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roadmap_items", sa.Column("source_team", sa.String(length=160), nullable=True))
    op.create_table(
        "roadmap_forecast_allocations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("roadmap_item_id", sa.Integer(), sa.ForeignKey("roadmap_items.id"), nullable=False),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("team_member_id", sa.Integer(), sa.ForeignKey("team_members.id"), nullable=False),
        sa.Column("bucket_id", sa.Integer(), sa.ForeignKey("buckets.id"), nullable=False),
        sa.Column("fiscal_month_id", sa.Integer(), sa.ForeignKey("fiscal_months.id"), nullable=False),
        sa.Column("hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "roadmap_item_id",
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            name="uq_roadmap_forecast_cell",
        ),
    )
    op.create_index("ix_roadmap_forecast_allocations_roadmap_item_id", "roadmap_forecast_allocations", ["roadmap_item_id"])
    op.create_index("ix_roadmap_forecast_allocations_product_id", "roadmap_forecast_allocations", ["product_id"])
    op.create_index("ix_roadmap_forecast_allocations_team_member_id", "roadmap_forecast_allocations", ["team_member_id"])
    op.create_index("ix_roadmap_forecast_allocations_fiscal_month_id", "roadmap_forecast_allocations", ["fiscal_month_id"])


def downgrade() -> None:
    op.drop_index("ix_roadmap_forecast_allocations_fiscal_month_id", table_name="roadmap_forecast_allocations")
    op.drop_index("ix_roadmap_forecast_allocations_team_member_id", table_name="roadmap_forecast_allocations")
    op.drop_index("ix_roadmap_forecast_allocations_product_id", table_name="roadmap_forecast_allocations")
    op.drop_index("ix_roadmap_forecast_allocations_roadmap_item_id", table_name="roadmap_forecast_allocations")
    op.drop_table("roadmap_forecast_allocations")
    op.drop_column("roadmap_items", "source_team")
