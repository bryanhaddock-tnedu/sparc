"""Store roadmap item schedule month highlights.

Revision ID: 0018_roadmap_schedule_months
Revises: 0017_promote_roadmap_allocations
Create Date: 2026-07-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0018_roadmap_schedule_months"
down_revision: str | None = "0017_promote_roadmap_allocations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roadmap_items", sa.Column("roadmap_schedule_months", sa.JSON(), nullable=True))
    op.execute("UPDATE roadmap_items SET roadmap_schedule_months = '[]' WHERE roadmap_schedule_months IS NULL")
    op.alter_column("roadmap_items", "roadmap_schedule_months", nullable=False)


def downgrade() -> None:
    op.drop_column("roadmap_items", "roadmap_schedule_months")
