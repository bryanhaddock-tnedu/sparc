"""Promote roadmap planner hours to product forecasts.

Revision ID: 0017_promote_roadmap_allocations
Revises: 0016_roadmap_item_schedule
Create Date: 2026-07-02
"""

from collections.abc import Sequence
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision: str = "0017_promote_roadmap_allocations"
down_revision: str | None = "0016_roadmap_item_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    rows = bind.execute(
        sa.text(
            """
            SELECT
                rfa.product_id,
                rfa.team_member_id,
                rfa.bucket_id,
                rfa.fiscal_month_id,
                fm.fiscal_year,
                COALESCE(SUM(rfa.hours), 0) AS hours
            FROM roadmap_forecast_allocations rfa
            JOIN fiscal_months fm ON fm.id = rfa.fiscal_month_id
            GROUP BY
                rfa.product_id,
                rfa.team_member_id,
                rfa.bucket_id,
                rfa.fiscal_month_id,
                fm.fiscal_year
            """
        )
    ).mappings().all()
    if not rows:
        return

    contexts = {(row["product_id"], row["team_member_id"], row["bucket_id"], row["fiscal_year"]) for row in rows}
    for product_id, team_member_id, bucket_id, fiscal_year in contexts:
        bind.execute(
            sa.text(
                """
                UPDATE forecast_entries
                SET hours = 0, updated_at = :updated_at
                WHERE product_id = :product_id
                  AND team_member_id = :team_member_id
                  AND bucket_id = :bucket_id
                  AND fiscal_month_id IN (
                    SELECT id FROM fiscal_months WHERE fiscal_year = :fiscal_year
                  )
                """
            ),
            {
                "updated_at": now,
                "product_id": product_id,
                "team_member_id": team_member_id,
                "bucket_id": bucket_id,
                "fiscal_year": fiscal_year,
            },
        )

    for row in rows:
        existing_id = bind.execute(
            sa.text(
                """
                SELECT id
                FROM forecast_entries
                WHERE product_id = :product_id
                  AND team_member_id = :team_member_id
                  AND bucket_id = :bucket_id
                  AND fiscal_month_id = :fiscal_month_id
                """
            ),
            row,
        ).scalar()
        if existing_id is None:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO forecast_entries (
                        product_id,
                        team_member_id,
                        bucket_id,
                        fiscal_month_id,
                        hours,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        :product_id,
                        :team_member_id,
                        :bucket_id,
                        :fiscal_month_id,
                        :hours,
                        :created_at,
                        :updated_at
                    )
                    """
                ),
                {
                    "product_id": row["product_id"],
                    "team_member_id": row["team_member_id"],
                    "bucket_id": row["bucket_id"],
                    "fiscal_month_id": row["fiscal_month_id"],
                    "hours": row["hours"],
                    "created_at": now,
                    "updated_at": now,
                },
            )
        else:
            bind.execute(
                sa.text(
                    """
                    UPDATE forecast_entries
                    SET hours = :hours, updated_at = :updated_at
                    WHERE id = :id
                    """
                ),
                {"hours": row["hours"], "updated_at": now, "id": existing_id},
            )

    bind.execute(sa.text("DELETE FROM roadmap_forecast_allocations"))


def downgrade() -> None:
    pass
