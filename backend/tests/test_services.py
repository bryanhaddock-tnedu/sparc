from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.seed import _seed_buckets
from app.models import Base, Product, TeamMember
from app.services.aggregations import product_summary
from app.services.costs import calculate_cost
from app.services.fiscal_year import fiscal_sequence_for_date, fiscal_year_for_date
from app.services.forecasting import upsert_forecast_entry


def test_fiscal_year_mapping():
    from datetime import date

    assert fiscal_year_for_date(date(2025, 7, 1)) == 2026
    assert fiscal_sequence_for_date(date(2025, 7, 1)) == 1
    assert fiscal_year_for_date(date(2026, 6, 30)) == 2026
    assert fiscal_sequence_for_date(date(2026, 6, 30)) == 12


def test_cost_calculation():
    assert calculate_cost(Decimal("12.5"), Decimal("100.00")) == 1250.0


def test_forecast_upsert_uniqueness():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()

        first = upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2026,
            month_sequence=1,
            hours=10,
        )
        second = upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2026,
            month_sequence=1,
            hours=14,
        )

        assert first.id == second.id
        assert second.hours == Decimal("14")


def test_product_summary_includes_budget_tracker_metrics():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS", budget_amount=Decimal("2000.00"))
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2026,
            month_sequence=1,
            hours=14,
        )

        summary = product_summary(db, product.id, 2026)

        assert summary["budget_amount"] == 2000.0
        assert summary["projected_spend"] == 1400.0
        assert summary["budget_remaining"] == 600.0
        assert summary["budget_utilization_percent"] == 70.0
