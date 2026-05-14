"""Add Product budget amount.

Revision ID: 0002_product_budget
Revises: 0001_initial
Create Date: 2026-05-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_product_budget"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column("budget_amount", sa.Numeric(precision=12, scale=2), nullable=False, server_default="0"),
    )
    op.alter_column("products", "budget_amount", server_default=None)


def downgrade() -> None:
    op.drop_column("products", "budget_amount")
