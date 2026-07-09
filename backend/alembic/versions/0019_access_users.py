"""Add SPARC local access users.

Revision ID: 0019_access_users
Revises: 0018_roadmap_schedule_months
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0019_access_users"
down_revision: str | None = "0018_roadmap_schedule_months"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=60), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("local_login_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("entra_tenant_id", sa.String(length=120), nullable=True),
        sa.Column("entra_object_id", sa.String(length=120), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("entra_tenant_id", "entra_object_id", name="uq_app_user_entra_identity"),
    )
    op.create_index("ix_app_users_email", "app_users", ["email"], unique=False)

    op.create_table(
        "user_program_area_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("program_area", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "program_area", name="uq_user_program_area_assignment"),
    )


def downgrade() -> None:
    op.drop_table("user_program_area_assignments")
    op.drop_index("ix_app_users_email", table_name="app_users")
    op.drop_table("app_users")
