from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.products import delete_product as delete_product_endpoint
from app.api.products import remove_product_team_member as remove_product_team_member_endpoint
from app.db.seed import _seed_buckets
from app.models import Base, ForecastEntry, JiraProjectCatalog, Product, ProductBudget, ProductTeamMember, TeamMember
from app.services.aggregations import dashboard_products, product_bucket_tables, product_summary
from app.services.costs import calculate_cost
from app.services.fiscal_year import fiscal_sequence_for_date, fiscal_year_for_date
from app.services.forecasting import upsert_forecast_entry
from app.services.jira_projects import add_product_jira_space, list_product_jira_spaces, update_product_jira_space


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


def test_forecast_upsert_creates_product_team_assignment():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
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
            hours=10,
        )

        assignment = db.scalar(
            select(ProductTeamMember).where(
                ProductTeamMember.product_id == product.id,
                ProductTeamMember.team_member_id == member.id,
            )
        )
        assert assignment is not None
        assert assignment.status == "active"


def test_product_summary_includes_budget_tracker_metrics():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add(ProductBudget(product_id=product.id, fiscal_year=2026, budget_amount=Decimal("2000.00")))

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


def test_product_budget_is_fiscal_year_specific():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add_all(
            [
                ProductBudget(product_id=product.id, fiscal_year=2026, budget_amount=Decimal("2000.00")),
                ProductBudget(product_id=product.id, fiscal_year=2027, budget_amount=Decimal("5000.00")),
            ]
        )

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2026,
            month_sequence=1,
            hours=14,
        )
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=14,
        )

        assert product_summary(db, product.id, 2026)["budget_amount"] == 2000.0
        assert product_summary(db, product.id, 2027)["budget_amount"] == 5000.0


def test_product_team_assignment_counts_without_forecast_hours():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS", budget_amount=Decimal("2000.00"))
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add(ProductTeamMember(product_id=product.id, team_member_id=member.id, status="active"))
        db.flush()

        rows = dashboard_products(db, 2026)

        assert rows[0]["team_members"] == 1
        assert rows[0]["forecasted_hours"] == 0


def test_product_bucket_tables_use_explicit_forecast_lines_for_bucket_rows():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add(ProductTeamMember(product_id=product.id, team_member_id=member.id, status="active"))
        db.flush()

        empty_tables = product_bucket_tables(db, product.id, 2026)

        assert all(bucket["rows"] == [] for bucket in empty_tables["buckets"])

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="ENHANCE",
            fiscal_year=2026,
            month_sequence=1,
            hours=0,
        )
        db.flush()

        tables = product_bucket_tables(db, product.id, 2026)

        buckets_with_rows = [bucket for bucket in tables["buckets"] if bucket["rows"]]
        assert [bucket["code"] for bucket in buckets_with_rows] == ["ENHANCE"]
        assert buckets_with_rows[0]["rows"][0]["team_member"] == "Avery Johnson"
        assert buckets_with_rows[0]["rows"][0]["totals"]["forecast_hours"] == 0


def test_removing_product_team_member_clears_product_forecast_lines():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="ENHANCE",
            fiscal_year=2026,
            month_sequence=1,
            hours=40,
        )
        assignment = db.scalar(
            select(ProductTeamMember).where(
                ProductTeamMember.product_id == product.id,
                ProductTeamMember.team_member_id == member.id,
            )
        )

        remove_product_team_member_endpoint(product.id, assignment.id, db)

        assert db.scalar(select(ForecastEntry)) is None
        assert db.scalar(select(ProductTeamMember)) is None
        assert all(bucket["rows"] == [] for bucket in product_bucket_tables(db, product.id, 2026)["buckets"])


def test_product_jira_space_mapping_uses_catalog_and_prevents_double_mapping():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first_product = Product(name="Student Information")
        second_product = Product(name="Educator Licensing")
        project = JiraProjectCatalog(
            jira_project_id="10001",
            jira_project_key="SIS",
            jira_project_name="Student Information System",
            project_type_key="software",
        )
        db.add_all([first_product, second_product, project])
        db.flush()

        mapping = add_product_jira_space(db, first_product.id, jira_project_catalog_id=project.id)
        db.flush()

        spaces = list_product_jira_spaces(db, first_product.id)
        assert mapping.jira_project_key == "SIS"
        assert spaces[0]["jira_project_name"] == "Student Information System"
        assert spaces[0]["validation_status"] == "valid"

        with pytest.raises(ValueError, match="already mapped"):
            add_product_jira_space(db, second_product.id, jira_project_catalog_id=project.id)


def test_product_jira_space_mapping_allows_multiple_projects_and_clears_scope():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(name="Core Infrastructure")
        first_project = JiraProjectCatalog(
            jira_project_id="10001",
            jira_project_key="GOV",
            jira_project_name="Governance",
            project_type_key="software",
        )
        second_project = JiraProjectCatalog(
            jira_project_id="10002",
            jira_project_key="RPA",
            jira_project_name="RPA",
            project_type_key="software",
        )
        db.add_all([product, first_project, second_project])
        db.flush()

        first_mapping = add_product_jira_space(
            db,
            product.id,
            jira_project_catalog_id=first_project.id,
            scope_jql="issuetype != Epic",
        )
        add_product_jira_space(db, product.id, jira_project_catalog_id=second_project.id)
        update_product_jira_space(db, product.id, first_mapping.id, {"scope_jql": None})
        db.flush()

        spaces = list_product_jira_spaces(db, product.id)

        assert [space["jira_project_key"] for space in spaces] == ["GOV", "RPA"]
        assert spaces[0]["scope_jql"] is None


def test_product_delete_requires_no_jira_project_mappings():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product = Product(name="Delete Me")
        mapped_product = Product(name="Keep Me")
        project = JiraProjectCatalog(
            jira_project_id="10001",
            jira_project_key="KEEP",
            jira_project_name="Keep Project",
            project_type_key="software",
        )
        db.add_all([product, mapped_product, project])
        db.flush()
        add_product_jira_space(db, mapped_product.id, jira_project_catalog_id=project.id)
        db.flush()

        assert delete_product_endpoint(product.id, db) == {"message": "Product deleted"}
        assert db.get(Product, product.id) is None
        with pytest.raises(Exception) as exc:
            delete_product_endpoint(mapped_product.id, db)

        assert getattr(exc.value, "status_code", None) == 409
