"""Add Jira project catalogue and product Jira spaces.

Revision ID: 0004_product_jira_spaces
Revises: 0003_product_team_members
Create Date: 2026-05-18
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_product_jira_spaces"
down_revision: str | None = "0003_product_team_members"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jira_project_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jira_project_id", sa.String(length=80), nullable=False),
        sa.Column("jira_project_key", sa.String(length=80), nullable=False),
        sa.Column("jira_project_name", sa.String(length=160), nullable=False),
        sa.Column("project_type_key", sa.String(length=80), nullable=True),
        sa.Column("is_visible", sa.Boolean(), nullable=False),
        sa.Column("is_archived", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_project_id"),
        sa.UniqueConstraint("jira_project_key"),
    )
    op.create_index(op.f("ix_jira_project_catalog_jira_project_key"), "jira_project_catalog", ["jira_project_key"], unique=True)

    op.create_table(
        "product_jira_spaces",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("jira_project_catalog_id", sa.Integer(), nullable=True),
        sa.Column("jira_project_id", sa.String(length=80), nullable=True),
        sa.Column("jira_project_key", sa.String(length=80), nullable=False),
        sa.Column("jira_project_name", sa.String(length=160), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("scope_jql", sa.Text(), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=False),
        sa.Column("validation_message", sa.Text(), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["jira_project_catalog_id"], ["jira_project_catalog.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("jira_project_key", name="uq_product_jira_space_key"),
        sa.UniqueConstraint("product_id", "jira_project_key", name="uq_product_jira_space_product_key"),
    )


def downgrade() -> None:
    op.drop_table("product_jira_spaces")
    op.drop_index(op.f("ix_jira_project_catalog_jira_project_key"), table_name="jira_project_catalog")
    op.drop_table("jira_project_catalog")
