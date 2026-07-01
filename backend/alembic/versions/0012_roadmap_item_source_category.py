"""Store source roadmap category.

Revision ID: 0012_roadmap_item_source_category
Revises: 0011_roadmap_item_fiscal_year
Create Date: 2026-07-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0012_roadmap_item_source_category"
down_revision: str | None = "0011_roadmap_item_fiscal_year"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roadmap_items", sa.Column("source_category", sa.String(length=160), nullable=True))


def downgrade() -> None:
    op.drop_column("roadmap_items", "source_category")
