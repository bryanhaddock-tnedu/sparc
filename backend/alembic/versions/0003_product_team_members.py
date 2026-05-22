"""Add product team member assignments.

Revision ID: 0003_product_team_members
Revises: 0002_product_budget
Create Date: 2026-05-14
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_product_team_members"
down_revision: str | None = "0002_product_budget"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_team_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("team_member_id", sa.Integer(), nullable=False),
        sa.Column("default_bucket_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["default_bucket_id"], ["buckets.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["team_member_id"], ["team_members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "team_member_id", name="uq_product_team_member"),
    )

    forecast_entries = sa.table(
        "forecast_entries",
        sa.column("product_id", sa.Integer()),
        sa.column("team_member_id", sa.Integer()),
        sa.column("bucket_id", sa.Integer()),
    )
    product_team_members = sa.table(
        "product_team_members",
        sa.column("product_id", sa.Integer()),
        sa.column("team_member_id", sa.Integer()),
        sa.column("default_bucket_id", sa.Integer()),
        sa.column("status", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    op.execute(
        product_team_members.insert().from_select(
            ["product_id", "team_member_id", "default_bucket_id", "status", "created_at", "updated_at"],
            sa.select(
                forecast_entries.c.product_id,
                forecast_entries.c.team_member_id,
                sa.func.min(forecast_entries.c.bucket_id),
                sa.literal("active"),
                sa.func.now(),
                sa.func.now(),
            ).group_by(forecast_entries.c.product_id, forecast_entries.c.team_member_id),
        )
    )


def downgrade() -> None:
    op.drop_table("product_team_members")
