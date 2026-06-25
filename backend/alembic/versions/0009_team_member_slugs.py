"""Add team member slugs.

Revision ID: 0009_team_member_slugs
Revises: 0008_product_slugs
Create Date: 2026-06-24
"""

from collections.abc import Sequence
import re
import unicodedata

from alembic import op
import sqlalchemy as sa

revision: str = "0009_team_member_slugs"
down_revision: str | None = "0008_product_slugs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("team_members")}
    if "slug" not in columns:
        op.add_column("team_members", sa.Column("slug", sa.String(length=180), nullable=True))

    members = bind.execute(sa.text("SELECT id, name, slug FROM team_members ORDER BY id")).mappings().all()
    used: set[str] = set()
    for member in members:
        current_slug = member["slug"]
        slug = current_slug.strip() if isinstance(current_slug, str) and current_slug.strip() else _slugify(member["name"])
        base_slug = slug
        suffix = 2
        while slug in used:
            slug = f"{base_slug}-{suffix}"
            suffix += 1
        used.add(slug)
        bind.execute(sa.text("UPDATE team_members SET slug = :slug WHERE id = :id"), {"slug": slug, "id": member["id"]})

    indexes = {index["name"] for index in inspector.get_indexes("team_members")}
    if "ix_team_members_slug" not in indexes:
        op.create_index("ix_team_members_slug", "team_members", ["slug"], unique=True)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("team_members")}
    if "ix_team_members_slug" in indexes:
        op.drop_index("ix_team_members_slug", table_name="team_members")
    columns = {column["name"] for column in inspector.get_columns("team_members")}
    if "slug" in columns:
        op.drop_column("team_members", "slug")


def _slugify(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")
    return slug or "team-member"
