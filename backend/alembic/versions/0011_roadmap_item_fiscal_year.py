"""Scope roadmap items by fiscal year.

Revision ID: 0011_roadmap_item_fiscal_year
Revises: 0010_roadmap_items
Create Date: 2026-07-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0011_roadmap_item_fiscal_year"
down_revision: str | None = "0010_roadmap_items"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roadmap_items", sa.Column("fiscal_year", sa.Integer(), server_default="2027", nullable=False))
    op.create_index("ix_roadmap_items_fiscal_year", "roadmap_items", ["fiscal_year"])
    op.alter_column("roadmap_items", "fiscal_year", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_roadmap_items_fiscal_year", table_name="roadmap_items")
    op.drop_column("roadmap_items", "fiscal_year")
