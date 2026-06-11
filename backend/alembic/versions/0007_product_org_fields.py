"""Add product org fields.

Revision ID: 0007_product_org_fields
Revises: 0006_product_fiscal_budgets
Create Date: 2026-06-11
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_product_org_fields"
down_revision: str | None = "0006_product_fiscal_budgets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("products")}
    if "office" not in columns:
        op.add_column("products", sa.Column("office", sa.String(length=80), nullable=True))
    if "division" not in columns:
        op.add_column("products", sa.Column("division", sa.String(length=160), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("products")}
    if "division" in columns:
        op.drop_column("products", "division")
    if "office" in columns:
        op.drop_column("products", "office")
