"""Add fiscal-year product budgets.

Revision ID: 0006_product_fiscal_budgets
Revises: 0005_estimation_foundation
Create Date: 2026-05-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_product_fiscal_budgets"
down_revision: str | None = "0005_estimation_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_budgets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("budget_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "fiscal_year", name="uq_product_budget_product_fiscal_year"),
    )
    op.create_index(op.f("ix_product_budgets_fiscal_year"), "product_budgets", ["fiscal_year"], unique=False)
    op.execute(
        """
        INSERT INTO product_budgets (product_id, fiscal_year, budget_amount, created_at, updated_at)
        SELECT id, 2026, budget_amount, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM products
        WHERE budget_amount IS NOT NULL AND budget_amount > 0
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_product_budgets_fiscal_year"), table_name="product_budgets")
    op.drop_table("product_budgets")
