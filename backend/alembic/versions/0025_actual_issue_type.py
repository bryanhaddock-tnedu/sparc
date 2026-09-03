"""Store Jira issue type on actual worklogs.

Revision ID: 0025_actual_issue_type
Revises: 0024_pm_estimation_profile
Create Date: 2026-09-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0025_actual_issue_type"
down_revision: str | None = "0024_pm_estimation_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("actual_entries", sa.Column("source_issue_type", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("actual_entries", "source_issue_type")
