"""Add product slugs.

Revision ID: 0008_product_slugs
Revises: 0007_product_org_fields
Create Date: 2026-06-24
"""

from collections.abc import Sequence
import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision: str = "0008_product_slugs"
down_revision: str | None = "0007_product_org_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("products")}
    if "slug" not in columns:
        op.add_column("products", sa.Column("slug", sa.String(length=180), nullable=True))

    products = bind.execute(sa.text("SELECT id, name, slug FROM products ORDER BY id")).mappings().all()
    used: set[str] = set()
    for product in products:
        current_slug = product["slug"]
        slug = current_slug.strip() if isinstance(current_slug, str) and current_slug.strip() else _slugify(product["name"])
        base_slug = slug
        suffix = 2
        while slug in used:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used.add(slug)
        bind.execute(sa.text("UPDATE products SET slug = :slug WHERE id = :id"), {"slug": slug, "id": product["id"]})

    indexes = {index["name"] for index in inspector.get_indexes("products")}
    if "ix_products_slug" not in indexes:
        op.create_index("ix_products_slug", "products", ["slug"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("products")}
    if "ix_products_slug" in indexes:
        op.drop_index("ix_products_slug", table_name="products")
    columns = {column["name"] for column in inspector.get_columns("products")}
    if "slug" in columns:
        op.drop_column("products", "slug")


def _slugify(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "product"
