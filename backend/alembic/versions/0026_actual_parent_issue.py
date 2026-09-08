"""Store Jira parent issue on actual worklogs.

Revision ID: 0026_actual_parent_issue
Revises: 0025_actual_issue_type
Create Date: 2026-09-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0026_actual_parent_issue"
down_revision: str | None = "0025_actual_issue_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("actual_entries", sa.Column("source_parent_ticket_key", sa.String(length=80), nullable=True))
    op.add_column("actual_entries", sa.Column("source_parent_ticket_summary", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("actual_entries", "source_parent_ticket_summary")
    op.drop_column("actual_entries", "source_parent_ticket_key")
