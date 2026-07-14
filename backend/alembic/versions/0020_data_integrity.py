"""Unify mapping ownership and preserve planning history.

Revision ID: 0020_data_integrity
Revises: 0019_access_users
Create Date: 2026-07-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0020_data_integrity"
down_revision: str | None = "0019_access_users"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "roadmap_items",
        sa.Column("product_mapping_source", sa.String(length=20), nullable=True, server_default="sync"),
    )
    op.add_column(
        "roadmap_items",
        sa.Column("bucket_mapping_source", sa.String(length=20), nullable=True, server_default="sync"),
    )
    op.execute("UPDATE roadmap_items SET product_mapping_source = 'manual' WHERE product_id IS NOT NULL")
    op.execute("UPDATE roadmap_items SET bucket_mapping_source = 'manual' WHERE bucket_id IS NOT NULL")
    op.alter_column("roadmap_items", "product_mapping_source", nullable=False, server_default=None)
    op.alter_column("roadmap_items", "bucket_mapping_source", nullable=False, server_default=None)

    op.execute(
        """
        UPDATE jira_product_mappings AS legacy
        SET product_id = canonical.product_id
        FROM product_jira_spaces AS canonical
        WHERE canonical.jira_project_key = legacy.jira_project_key
          AND canonical.is_active = TRUE
        """
    )
    op.execute(
        """
        UPDATE jira_product_mappings AS legacy
        SET product_id = NULL
        WHERE NOT EXISTS (
            SELECT 1
            FROM product_jira_spaces AS canonical
            WHERE canonical.jira_project_key = legacy.jira_project_key
              AND canonical.is_active = TRUE
        )
        """
    )

    op.drop_constraint(
        "forecast_recommendation_decision_applied_forecast_entry_id_fkey",
        "forecast_recommendation_decisions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_forecast_rec_applied_entry",
        "forecast_recommendation_decisions",
        "forecast_entries",
        ["applied_forecast_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_table("roadmap_forecast_allocations")


def downgrade() -> None:
    op.create_table(
        "roadmap_forecast_allocations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("roadmap_item_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("team_member_id", sa.Integer(), nullable=False),
        sa.Column("bucket_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_month_id", sa.Integer(), nullable=False),
        sa.Column("hours", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["fiscal_month_id"], ["fiscal_months.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["roadmap_item_id"], ["roadmap_items.id"]),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "roadmap_item_id",
            "product_id",
            "team_member_id",
            "bucket_id",
            "fiscal_month_id",
            name="uq_roadmap_forecast_cell",
        ),
    )
    op.create_index(
        "ix_roadmap_forecast_allocations_fiscal_month_id",
        "roadmap_forecast_allocations",
        ["fiscal_month_id"],
    )
    op.create_index("ix_roadmap_forecast_allocations_product_id", "roadmap_forecast_allocations", ["product_id"])
    op.create_index("ix_roadmap_forecast_allocations_roadmap_item_id", "roadmap_forecast_allocations", ["roadmap_item_id"])
    op.create_index("ix_roadmap_forecast_allocations_team_member_id", "roadmap_forecast_allocations", ["team_member_id"])

    op.drop_constraint("fk_forecast_rec_applied_entry", "forecast_recommendation_decisions", type_="foreignkey")
    op.create_foreign_key(
        "forecast_recommendation_decision_applied_forecast_entry_id_fkey",
        "forecast_recommendation_decisions",
        "forecast_entries",
        ["applied_forecast_entry_id"],
        ["id"],
    )

    op.drop_column("roadmap_items", "bucket_mapping_source")
    op.drop_column("roadmap_items", "product_mapping_source")
