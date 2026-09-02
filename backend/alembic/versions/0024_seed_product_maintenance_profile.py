"""Seed Product Maintenance Jira Team estimation profile.

Revision ID: 0024_pm_estimation_profile
Revises: 0023_ticket_cost_receipts
Create Date: 2026-09-02
"""

from collections.abc import Sequence

from alembic import op


revision: str = "0024_pm_estimation_profile"
down_revision: str | None = "0023_ticket_cost_receipts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO jira_team_estimation_profiles (
            jira_team,
            velocity_story_points,
            developer_capacity_hours,
            qa_percent_of_developer_hours,
            product_owner_percent_of_developer_hours,
            is_active,
            notes,
            created_at,
            updated_at
        )
        SELECT
            'Product Maintenance',
            75.8,
            360,
            0.20,
            0.15,
            true,
            'Seeded from SPARC-3 Product Maintenance estimation decision: 75.8 SP velocity, 6 developers at 60 sprint hours each, QA at 20% of developer hours, Product Owner at 15% of developer hours.',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        WHERE NOT EXISTS (
            SELECT 1
            FROM jira_team_estimation_profiles
            WHERE lower(jira_team) = lower('Product Maintenance')
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM jira_team_estimation_profiles
        WHERE jira_team = 'Product Maintenance'
          AND notes = 'Seeded from SPARC-3 Product Maintenance estimation decision: 75.8 SP velocity, 6 developers at 60 sprint hours each, QA at 20% of developer hours, Product Owner at 15% of developer hours.'
        """
    )
