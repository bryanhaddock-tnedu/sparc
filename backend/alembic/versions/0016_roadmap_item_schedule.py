"""Store roadmap item source schedule dates.

Revision ID: 0016_roadmap_item_schedule
Revises: 0015_roadmap_forecast_plan
Create Date: 2026-07-02
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0016_roadmap_item_schedule"
down_revision: str | None = "0015_roadmap_forecast_plan"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("roadmap_items", sa.Column("roadmap_start_date", sa.Date(), nullable=True))
    op.add_column("roadmap_items", sa.Column("roadmap_end_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("roadmap_items", "roadmap_end_date")
    op.drop_column("roadmap_items", "roadmap_start_date")
