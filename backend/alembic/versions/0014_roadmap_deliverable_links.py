"""Add product-scoped roadmap deliverable link metadata.

Revision ID: 0014_roadmap_deliverable_links
Revises: 0013_forecast_recommendation_decisions
Create Date: 2026-07-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0014_roadmap_deliverable_links"
down_revision: str | None = "0013_forecast_recommendation_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roadmap_item_issue_links", sa.Column("product_id", sa.Integer(), nullable=True))
    op.add_column("roadmap_item_issue_links", sa.Column("bucket_id", sa.Integer(), nullable=True))
    op.add_column("roadmap_item_issue_links", sa.Column("issue_type", sa.String(length=120), nullable=True))
    op.add_column("roadmap_item_issue_links", sa.Column("status", sa.String(length=120), nullable=True))
    op.add_column("roadmap_item_issue_links", sa.Column("status_category", sa.String(length=80), nullable=True))
    op.add_column("roadmap_item_issue_links", sa.Column("source_category", sa.String(length=160), nullable=True))
    op.create_foreign_key("fk_roadmap_item_issue_links_product_id", "roadmap_item_issue_links", "products", ["product_id"], ["id"])
    op.create_foreign_key("fk_roadmap_item_issue_links_bucket_id", "roadmap_item_issue_links", "buckets", ["bucket_id"], ["id"])
    op.create_index("ix_roadmap_item_issue_links_product_id", "roadmap_item_issue_links", ["product_id"])


def downgrade() -> None:
    op.drop_index("ix_roadmap_item_issue_links_product_id", table_name="roadmap_item_issue_links")
    op.drop_constraint("fk_roadmap_item_issue_links_bucket_id", "roadmap_item_issue_links", type_="foreignkey")
    op.drop_constraint("fk_roadmap_item_issue_links_product_id", "roadmap_item_issue_links", type_="foreignkey")
    op.drop_column("roadmap_item_issue_links", "source_category")
    op.drop_column("roadmap_item_issue_links", "status_category")
    op.drop_column("roadmap_item_issue_links", "status")
    op.drop_column("roadmap_item_issue_links", "issue_type")
    op.drop_column("roadmap_item_issue_links", "bucket_id")
    op.drop_column("roadmap_item_issue_links", "product_id")
