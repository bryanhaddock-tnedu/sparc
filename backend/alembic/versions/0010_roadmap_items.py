"""Add roadmap item billing attribution tables.

Revision ID: 0010_roadmap_items
Revises: 0009_team_member_slugs
Create Date: 2026-06-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010_roadmap_items"
down_revision: str | None = "0009_team_member_slugs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "roadmap_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("bucket_id", sa.Integer(), nullable=True),
        sa.Column("jira_issue_id", sa.String(length=120), nullable=False),
        sa.Column("jira_issue_key", sa.String(length=80), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=120), nullable=True),
        sa.Column("status_category", sa.String(length=80), nullable=True),
        sa.Column("issue_type", sa.String(length=120), nullable=True),
        sa.Column("program_area", sa.String(length=160), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_payload_hash", sa.String(length=128), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "jira_issue_id", name="uq_roadmap_item_source_issue_id"),
        sa.UniqueConstraint("source", "jira_issue_key", name="uq_roadmap_item_source_issue_key"),
    )
    op.create_index("ix_roadmap_items_jira_issue_key", "roadmap_items", ["jira_issue_key"])
    op.create_index("ix_roadmap_items_product_id", "roadmap_items", ["product_id"])

    op.create_table(
        "roadmap_item_issue_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("roadmap_item_id", sa.Integer(), nullable=False),
        sa.Column("jira_issue_id", sa.String(length=120), nullable=True),
        sa.Column("jira_issue_key", sa.String(length=80), nullable=False),
        sa.Column("jira_issue_summary", sa.Text(), nullable=True),
        sa.Column("jira_project_key", sa.String(length=80), nullable=True),
        sa.Column("relationship_type", sa.String(length=120), nullable=True),
        sa.Column("source", sa.String(length=80), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["roadmap_item_id"], ["roadmap_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("roadmap_item_id", "jira_issue_key", name="uq_roadmap_item_issue_link"),
    )
    op.create_index("ix_roadmap_item_issue_links_jira_issue_key", "roadmap_item_issue_links", ["jira_issue_key"])
    op.create_index("ix_roadmap_item_issue_links_roadmap_item_id", "roadmap_item_issue_links", ["roadmap_item_id"])


def downgrade() -> None:
    op.drop_index("ix_roadmap_item_issue_links_roadmap_item_id", table_name="roadmap_item_issue_links")
    op.drop_index("ix_roadmap_item_issue_links_jira_issue_key", table_name="roadmap_item_issue_links")
    op.drop_table("roadmap_item_issue_links")
    op.drop_index("ix_roadmap_items_product_id", table_name="roadmap_items")
    op.drop_index("ix_roadmap_items_jira_issue_key", table_name="roadmap_items")
    op.drop_table("roadmap_items")
