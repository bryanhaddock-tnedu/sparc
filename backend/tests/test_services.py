from datetime import date, datetime, time, timezone
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from openpyxl import load_workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.products import create_product as create_product_endpoint
from app.api.products import delete_product as delete_product_endpoint
from app.api.products import get_product as get_product_endpoint
from app.api.products import remove_product_team_member as remove_product_team_member_endpoint
from app.api.team_members import create_team_member as create_team_member_endpoint
from app.api.team_members import get_team_member as get_team_member_endpoint
from app.db.seed import _seed_buckets
from app.models import (
    ActualEntry,
    AttributionChange,
    Base,
    Bucket,
    ForecastEntry,
    ForecastRecommendationDecision,
    JiraProductMapping,
    JiraProjectCatalog,
    Product,
    ProductBudget,
    ProductJiraSpace,
    ProductTeamMember,
    RoadmapItem,
    RoadmapItemIssueLink,
    SyncRun,
    TeamMember,
)
from app.schemas import ProductCreate, TeamMemberCreate
from app.services.aggregations import dashboard_labor_mix, dashboard_products, dashboard_work_type_breakdown, product_bucket_tables, product_summary
from app.services.costs import calculate_cost
from app.services.fiscal_year import current_fiscal_year, fiscal_sequence_for_date, fiscal_year_for_date, get_fiscal_month
from app.services.forecasting import remove_empty_forecast_line, upsert_forecast_entry
from app.services.roadmap_forecasting import team_roadmap_forecast_plan, upsert_team_roadmap_forecast_allocations
from app.services.forecast_recommendations import (
    create_forecast_recommendation_decision,
    list_forecast_recommendation_decisions,
)
from app.services.reporting import build_labor_cost_report, build_labor_cost_report_workbook
from app.services.access_control import local_disabled_admin
from app.services.jira_projects import (
    JiraProjectPayload,
    add_product_jira_space,
    list_product_jira_spaces,
    move_product_jira_space,
    remove_product_jira_space,
    update_jira_project_catalog_visibility,
    update_product_jira_space,
)
from app.services.jira_auto_sync import has_live_sync_for_local_date, is_daily_sync_catch_up_window, next_daily_run_at
from app.services import jira_projects
from app.services.roadmap import (
    RoadmapIssueLinkPayload,
    RoadmapIssuePayload,
    UNSCOPED_ROADMAP_FISCAL_YEAR,
    _enrich_roadmap_payload_links,
    _has_fiscal_year_label,
    _jira_date_field_ids_by_name,
    _normalize_roadmap_issue,
    _parse_jira_date,
    _replace_roadmap_issue_links,
    _remove_stale_roadmap_items_from_fiscal_year,
    _roadmap_fiscal_year_label,
    _upsert_roadmap_item,
    list_roadmap_items,
    map_roadmap_ticket,
    product_roadmap_items,
    roadmap_actual_rows,
    update_roadmap_item_mapping,
)


def test_fiscal_year_mapping():
    from datetime import date

    assert fiscal_year_for_date(date(2025, 7, 1)) == 2026
    assert fiscal_sequence_for_date(date(2025, 7, 1)) == 1
    assert fiscal_year_for_date(date(2026, 6, 30)) == 2026
    assert fiscal_sequence_for_date(date(2026, 6, 30)) == 12
    assert current_fiscal_year(date(2026, 7, 1)) == 2027


def test_next_daily_jira_sync_runs_before_8am_central():
    run_time = time(hour=7, minute=30)
    timezone_name = "America/Chicago"

    before_schedule = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
    next_run = next_daily_run_at(before_schedule, run_time, timezone_name)
    next_run_local = next_run.astimezone(ZoneInfo(timezone_name))

    assert next_run_local.date() == date(2026, 7, 2)
    assert next_run_local.time() == run_time
    assert next_run_local.hour < 8

    after_schedule = datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc)
    following_run = next_daily_run_at(after_schedule, run_time, timezone_name).astimezone(ZoneInfo(timezone_name))

    assert following_run.date() == date(2026, 7, 3)
    assert following_run.time() == run_time


def test_daily_jira_sync_catches_up_before_8am_central():
    run_time = time(hour=7, minute=30)
    timezone_name = "America/Chicago"

    before_cutoff = datetime(2026, 7, 2, 12, 45, tzinfo=timezone.utc)
    at_cutoff = datetime(2026, 7, 2, 13, 0, tzinfo=timezone.utc)

    assert is_daily_sync_catch_up_window(before_cutoff, run_time, timezone_name)
    assert not is_daily_sync_catch_up_window(at_cutoff, run_time, timezone_name)


def test_scheduled_jira_sync_detects_existing_central_day_run():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(
            SyncRun(
                source="jira",
                mode="live",
                status="completed",
                started_at=datetime(2026, 7, 2, 12, 20, tzinfo=timezone.utc),
            )
        )
        db.flush()

        assert has_live_sync_for_local_date(db, date(2026, 7, 2), "America/Chicago")
        assert not has_live_sync_for_local_date(db, date(2026, 7, 3), "America/Chicago")


def test_cost_calculation():
    assert calculate_cost(Decimal("12.5"), Decimal("100.00")) == 1250.0


def test_labor_cost_report_rolls_up_by_team_and_bucket():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Akhil Musani", slug="akhil-musani", role="QA", team="Product Maintenance", bill_rate=Decimal("80"))
        db.add_all([product, member])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=10,
        )
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=2,
            hours=5,
        )

        report = build_labor_cost_report(db, 2027, dimensions=["team", "bucket"], sort_metric="forecast_cost")

        assert report["dimensions"] == [{"key": "team", "label": "Team"}, {"key": "bucket", "label": "Bucket"}]
        assert len(report["rows"]) == 1
        row = report["rows"][0]
        assert [value["label"] for value in row["dimension_values"]] == ["Product Maintenance", "Net New"]
        assert row["forecast_hours"] == 15
        assert row["forecast_cost"] == 1200
        assert report["totals"]["forecast_cost"] == 1200


def test_labor_cost_report_rolls_up_by_role_and_bucket():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        engineer = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Apps", bill_rate=Decimal("100"))
        qa = TeamMember(name="Jamie Reyes", slug="jamie-reyes", role="QA", team="Apps", bill_rate=Decimal("80"))
        db.add_all([product, engineer, qa])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=engineer.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=10,
        )
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=qa.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=5,
        )

        report = build_labor_cost_report(db, 2027, dimensions=["role", "bucket"], sort_metric="role")

        assert report["dimensions"] == [{"key": "role", "label": "Role"}, {"key": "bucket", "label": "Bucket"}]
        assert [[value["label"] for value in row["dimension_values"]] for row in report["rows"]] == [
            ["Engineer", "Net New"],
            ["QA", "Net New"],
        ]
        assert [row["forecast_cost"] for row in report["rows"]] == [1000, 400]
        assert report["totals"]["forecast_cost"] == 1400


def test_labor_cost_report_rolls_up_by_budget_dimensions_with_employment_type():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Accountability", slug="accountability")
        employee = TeamMember(
            name="Avery Johnson",
            slug="avery-johnson",
            role="Engineer",
            team="Apps",
            employment_type="Employee",
            bill_rate=Decimal("100"),
        )
        contractor = TeamMember(
            name="Jamie Reyes",
            slug="jamie-reyes",
            role="Engineer",
            team="Apps",
            employment_type="Contractor",
            bill_rate=Decimal("80"),
        )
        db.add_all([product, employee, contractor])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=employee.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=10,
        )
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=contractor.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=5,
        )

        report = build_labor_cost_report(
            db,
            2027,
            dimensions=["product", "bucket", "role", "employment_type"],
            sort_metric="employment_type",
        )

        assert report["dimensions"] == [
            {"key": "product", "label": "Product"},
            {"key": "bucket", "label": "Bucket"},
            {"key": "role", "label": "Role"},
            {"key": "employment_type", "label": "Employment Type"},
        ]
        assert [[value["label"] for value in row["dimension_values"]] for row in report["rows"]] == [
            ["Accountability", "Net New", "Engineer", "Contractor"],
            ["Accountability", "Net New", "Engineer", "Employee"],
        ]
        assert [row["forecast_hours"] for row in report["rows"]] == [5, 10]
        assert [row["forecast_cost"] for row in report["rows"]] == [400, 1000]
        assert report["totals"]["forecast_cost"] == 1400


def test_labor_cost_report_sorts_by_selected_dimension():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        zeta = Product(name="Zeta Product", slug="zeta-product")
        alpha = Product(name="Alpha Product", slug="alpha-product")
        member = TeamMember(name="Akhil Musani", slug="akhil-musani", role="QA", team="QA", bill_rate=Decimal("80"))
        db.add_all([zeta, alpha, member])
        db.flush()

        for product in (zeta, alpha):
            upsert_forecast_entry(
                db,
                product_id=product.id,
                team_member_id=member.id,
                bucket_code="ENHANCE",
                fiscal_year=2027,
                month_sequence=1,
                hours=4,
            )

        report = build_labor_cost_report(db, 2027, dimensions=["product", "bucket"], sort_metric="product")

        assert [row["dimension_values"][0]["label"] for row in report["rows"]] == ["Alpha Product", "Zeta Product"]


def test_labor_cost_report_workbook_exports_xlsx():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="SWORD", slug="sword")
        member = TeamMember(name="Akhil Musani", slug="akhil-musani", role="QA", team="QA", bill_rate=Decimal("80"))
        db.add_all([product, member])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="ENHANCE",
            fiscal_year=2027,
            month_sequence=1,
            hours=4,
        )

        workbook_bytes = build_labor_cost_report_workbook(
            db,
            2027,
            dimensions=["product", "bucket", "role", "employment_type"],
            sort_metric="forecast_cost",
        )
        workbook = load_workbook(BytesIO(workbook_bytes.getvalue()), data_only=True)
        worksheet = workbook["Labor Cost"]

        assert worksheet["A1"].value == "SPARC Labor Cost Report"
        assert worksheet["A4"].value == "Product"
        assert worksheet["B4"].value == "Bucket"
        assert worksheet["C4"].value == "Role"
        assert worksheet["D4"].value == "Employment Type"
        assert worksheet["A5"].value == "SWORD"
        assert worksheet["B5"].value == "Enhance"
        assert worksheet["C5"].value == "QA"
        assert worksheet["D5"].value == "Employee"
        assert worksheet["F5"].value == 320


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


def test_team_roadmap_forecast_allocations_roll_up_to_forecast():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="TNSD", slug="tnsd")
        member = TeamMember(name="Rojina Thapa", slug="rojina-thapa", role="QA", team="Product Maintenance", bill_rate=Decimal("70"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="100159",
            jira_issue_key="ROADMAP-159",
            title="Automate data update",
            issue_type="Idea",
            source_team="Product Maintenance",
            roadmap_start_date=date(2026, 9, 1),
            roadmap_end_date=date(2026, 11, 30),
            roadmap_schedule_months=[3, 4, 5],
        )
        db.add(roadmap_item)
        db.flush()
        db.add(
            RoadmapItemIssueLink(
                roadmap_item_id=roadmap_item.id,
                product_id=product.id,
                bucket_id=bucket.id,
                jira_issue_id="200266",
                jira_issue_key="TNSD-266",
                jira_issue_summary="TNSD continuous maintenance",
                jira_project_key="TNSD",
                relationship_type="Delivery",
                issue_type="Deliverable",
                status="In Progress",
                status_category="In Progress",
                source_category="Maintenance",
            )
        )
        db.flush()

        result = upsert_team_roadmap_forecast_allocations(
            db,
            "product-maintenance",
            2027,
            [
                {
                    "roadmap_item_id": roadmap_item.id,
                    "product_id": product.id,
                    "team_member_id": member.id,
                    "bucket_id": bucket.id,
                    "fiscal_year": 2027,
                    "month_sequence": 1,
                    "hours": Decimal("12"),
                }
            ],
        )

        forecast = db.scalar(select(ForecastEntry))
        assert forecast is not None
        assert forecast.product_id == product.id
        assert forecast.team_member_id == member.id
        assert forecast.bucket_id == bucket.id
        assert forecast.hours == Decimal("12")
        assert result["team"] == "Product Maintenance"
        assert result["rows"][0]["forecast_hours"] == Decimal("12")
        assert result["rows"][0]["roadmap_start_date"] == date(2026, 9, 1)
        assert result["rows"][0]["roadmap_end_date"] == date(2026, 11, 30)
        assert result["rows"][0]["roadmap_schedule_months"] == [3, 4, 5]
        assert result["rows"][0]["deliverables"][0]["jira_issue_key"] == "TNSD-266"
        assert result["rows"][0]["deliverables"][0]["jira_issue_summary"] == "TNSD continuous maintenance"

        cleared = upsert_team_roadmap_forecast_allocations(
            db,
            "Product Maintenance",
            2027,
            [
                {
                    "roadmap_item_id": roadmap_item.id,
                    "product_id": product.id,
                    "team_member_id": member.id,
                    "bucket_id": bucket.id,
                    "fiscal_year": 2027,
                    "month_sequence": 1,
                    "hours": Decimal("0"),
                }
            ],
        )

        assert db.scalar(select(ForecastEntry)).hours == Decimal("0")
        assert cleared["rows"][0]["forecast_hours"] == Decimal("0")


def test_team_roadmap_forecast_updates_only_submitted_months():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Ryan Daily", slug="ryan-daily", role="Sr. Dev", team="Product Maintenance", bill_rate=Decimal("0"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="100168",
            jira_issue_key="ROADMAP-168",
            title="Sam.Gov SAM.gov Submission History Enhancements",
            issue_type="Idea",
            source_team="Product Maintenance",
            roadmap_start_date=date(2026, 7, 1),
            roadmap_end_date=date(2026, 9, 30),
        )
        db.add(roadmap_item)
        db.flush()

        for month_sequence in range(1, 13):
            upsert_forecast_entry(
                db,
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_year=2027,
                month_sequence=month_sequence,
                hours=40,
            )

        upsert_team_roadmap_forecast_allocations(
            db,
            "Product Maintenance",
            2027,
            [
                {
                    "roadmap_item_id": roadmap_item.id,
                    "product_id": product.id,
                    "team_member_id": member.id,
                    "bucket_id": bucket.id,
                    "fiscal_year": 2027,
                    "month_sequence": month_sequence,
                    "hours": Decimal("40"),
                }
                for month_sequence in (1, 2, 3)
            ],
        )

        tables = product_bucket_tables(db, product.id, 2027)
        maintenance = next(bucket_payload for bucket_payload in tables["buckets"] if bucket_payload["code"] == "MAINTENANCE")
        row = next(member_row for member_row in maintenance["rows"] if member_row["team_member_id"] == member.id)

        assert [cell["forecast_hours"] for cell in row["months"]] == [40] * 12
        assert row["totals"]["forecast_hours"] == 480


def test_team_roadmap_forecast_rejects_inactive_products():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Retired Product", slug="retired-product", is_active=False)
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))

        with pytest.raises(ValueError, match="Inactive Products"):
            upsert_team_roadmap_forecast_allocations(
                db,
                "Applications",
                2027,
                [
                    {
                        "roadmap_item_id": None,
                        "product_id": product.id,
                        "team_member_id": member.id,
                        "bucket_id": bucket.id,
                        "fiscal_year": 2027,
                        "month_sequence": 1,
                        "hours": Decimal("10"),
                    }
                ],
            )


def test_team_roadmap_forecast_plan_uses_existing_product_forecast():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Ryan Daily", slug="ryan-daily", role="Sr. Dev", team="Product Maintenance", bill_rate=Decimal("0"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="100168",
            jira_issue_key="ROADMAP-168",
            title="Sam.Gov SAM.gov Submission History Enhancements",
            issue_type="Idea",
            source_team="Product Maintenance",
            roadmap_start_date=date(2026, 7, 1),
            roadmap_end_date=date(2026, 9, 30),
        )
        db.add(roadmap_item)
        db.flush()
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_id=bucket.id,
            fiscal_year=2027,
            month_sequence=1,
            hours=40,
        )

        result = team_roadmap_forecast_plan(db, "Product Maintenance", 2027)

        assert result["rows"][0]["forecast_hours"] == Decimal("40")
        assert result["rows"][0]["allocations"][0]["roadmap_item_id"] == roadmap_item.id
        assert result["rows"][0]["allocations"][0]["team_member_id"] == member.id
        assert result["rows"][0]["allocations"][0]["month_sequence"] == 1
        assert result["rows"][0]["allocations"][0]["hours"] == 40


def test_team_roadmap_forecast_plan_uses_existing_product_forecast_without_roadmap_item():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Lalitha Battini", slug="lalitha-battini", role="Dev", team="Product Maintenance", bill_rate=Decimal("82"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_id=bucket.id,
            fiscal_year=2027,
            month_sequence=1,
            hours=20,
        )

        result = team_roadmap_forecast_plan(db, "Product Maintenance", 2027)

        assert len(result["rows"]) == 1
        assert result["rows"][0]["roadmap_item_id"] is None
        assert result["rows"][0]["product"] == "Core Infrastructure"
        assert result["rows"][0]["bucket"] == "Maintenance"
        assert result["rows"][0]["forecast_hours"] == Decimal("20")
        assert result["rows"][0]["allocations"][0]["roadmap_item_id"] is None
        assert result["rows"][0]["allocations"][0]["team_member_id"] == member.id


def test_team_roadmap_forecast_plan_includes_assigned_product_bucket_without_roadmap_item():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Greg Marcum", slug="greg-marcum", role="Sr. Dev", team="Product Maintenance", bill_rate=Decimal("50"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        db.add(ProductTeamMember(product_id=product.id, team_member_id=member.id, default_bucket_id=bucket.id, status="active"))
        db.flush()

        result = team_roadmap_forecast_plan(db, "Product Maintenance", 2027)

        assert len(result["rows"]) == 1
        assert result["rows"][0]["roadmap_item_id"] is None
        assert result["rows"][0]["product"] == "Core Infrastructure"
        assert result["rows"][0]["bucket"] == "Maintenance"
        assert result["rows"][0]["forecast_hours"] == Decimal("0")
        assert result["rows"][0]["allocations"] == []


def test_team_roadmap_forecast_plan_saves_product_forecast_without_roadmap_item():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Ryan Daily", slug="ryan-daily", role="Sr. Dev", team="Product Maintenance", bill_rate=Decimal("0"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None

        result = upsert_team_roadmap_forecast_allocations(
            db,
            "Product Maintenance",
            2027,
            [
                {
                    "roadmap_item_id": None,
                    "product_id": product.id,
                    "team_member_id": member.id,
                    "bucket_id": bucket.id,
                    "fiscal_year": 2027,
                    "month_sequence": 1,
                    "hours": Decimal("40"),
                }
            ],
        )
        tables = product_bucket_tables(db, product.id, 2027)
        maintenance = next(bucket_payload for bucket_payload in tables["buckets"] if bucket_payload["code"] == "MAINTENANCE")
        row = next(member_row for member_row in maintenance["rows"] if member_row["team_member_id"] == member.id)

        assert result["rows"][0]["roadmap_item_id"] is None
        assert result["rows"][0]["forecast_hours"] == Decimal("40")
        assert result["rows"][0]["allocations"][0]["roadmap_item_id"] is None
        assert row["months"][0]["forecast_hours"] == 40


def test_team_roadmap_forecast_plan_retains_product_forecast_when_planning_rows_overlap():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        member = TeamMember(name="Lalitha Battini", slug="lalitha-battini", role="Dev", team="Product Maintenance", bill_rate=Decimal("82"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        db.add_all(
            [
                RoadmapItem(
                    source="jira_product_discovery",
                    fiscal_year=2027,
                    product_id=product.id,
                    bucket_id=bucket.id,
                    jira_issue_id="100168",
                    jira_issue_key="ROADMAP-168",
                    title="Sam.Gov SAM.gov Submission History Enhancements",
                    issue_type="Idea",
                    source_team="Product Maintenance",
                    roadmap_start_date=date(2026, 7, 1),
                    roadmap_end_date=date(2026, 9, 30),
                ),
                RoadmapItem(
                    source="jira_product_discovery",
                    fiscal_year=2027,
                    product_id=product.id,
                    bucket_id=bucket.id,
                    jira_issue_id="100180",
                    jira_issue_key="ROADMAP-180",
                    title="TDOE Application Portfolio Annual Maintenance",
                    issue_type="Idea",
                    source_team="Product Maintenance",
                    roadmap_start_date=date(2026, 7, 1),
                    roadmap_end_date=date(2026, 9, 30),
                ),
            ]
        )
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_id=bucket.id,
            fiscal_year=2027,
            month_sequence=1,
            hours=60,
        )

        result = team_roadmap_forecast_plan(db, "Product Maintenance", 2027)
        core_rows = [row for row in result["rows"] if row["product"] == "Core Infrastructure" and row["bucket"] == "Maintenance"]
        allocations = [allocation for row in core_rows for allocation in row["allocations"]]

        assert len(core_rows) == 2
        assert len(allocations) == 1
        assert allocations[0]["team_member_id"] == member.id
        assert allocations[0]["month_sequence"] == 1
        assert allocations[0]["hours"] == 60
        assert sum(row["forecast_hours"] for row in core_rows) == Decimal("60")


def test_team_roadmap_forecast_plan_scopes_linked_components_to_row_product():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        epso = Product(name="EPSO", slug="epso")
        sword = Product(name="SWORD", slug="sword")
        member = TeamMember(name="Rojina Thapa", slug="rojina-thapa", role="QA", team="Product Maintenance", bill_rate=Decimal("70"))
        db.add_all([epso, sword, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        db.add_all(
            [
                ProductTeamMember(product_id=epso.id, team_member_id=member.id, default_bucket_id=bucket.id, status="active"),
                ProductTeamMember(product_id=sword.id, team_member_id=member.id, default_bucket_id=bucket.id, status="active"),
            ]
        )
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            bucket_id=bucket.id,
            jira_issue_id="100180",
            jira_issue_key="ROADMAP-180",
            title="TDOE Application Portfolio Annual Maintenance",
            issue_type="Idea",
            source_team="Product Maintenance",
        )
        db.add(roadmap_item)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(
                    roadmap_item_id=roadmap_item.id,
                    product_id=epso.id,
                    bucket_id=bucket.id,
                    jira_issue_id="200054",
                    jira_issue_key="EPSO-54",
                    jira_issue_summary="FY27 EPSO Maintenance",
                    jira_project_key="EPSO",
                    relationship_type="Delivery",
                    issue_type="Deliverable",
                ),
                RoadmapItemIssueLink(
                    roadmap_item_id=roadmap_item.id,
                    product_id=sword.id,
                    bucket_id=bucket.id,
                    jira_issue_id="200974",
                    jira_issue_key="SWORD-974",
                    jira_issue_summary="SWORD continuous maintenance",
                    jira_project_key="SWORD",
                    relationship_type="Delivery",
                    issue_type="Story",
                ),
            ]
        )
        db.flush()

        result = team_roadmap_forecast_plan(db, "product-maintenance", 2027)
        rows = [row for row in result["rows"] if row["roadmap_item_key"] == "ROADMAP-180"]

        assert len(rows) == 2
        assert {row["product"] for row in rows} == {"EPSO", "SWORD"}
        rows_by_product = {row["product"]: row for row in rows}
        assert [deliverable["jira_issue_key"] for deliverable in rows_by_product["EPSO"]["deliverables"]] == ["EPSO-54"]
        assert [deliverable["jira_issue_key"] for deliverable in rows_by_product["SWORD"]["deliverables"]] == ["SWORD-974"]


def test_team_product_forecast_plan_uses_team_actuals_product_program_area_and_rate_redaction():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information", office="Academics")
        team_member = TeamMember(
            name="Avery Johnson",
            slug="avery-johnson",
            role="Engineer",
            team="Applications",
            bill_rate=Decimal("100"),
        )
        other_member = TeamMember(
            name="Morgan Smith",
            slug="morgan-smith",
            role="Engineer",
            team="Operations",
            bill_rate=Decimal("120"),
        )
        db.add_all([product, team_member, other_member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "ENHANCE"))
        month = get_fiscal_month(db, 2027, 1)
        db.add(ProductTeamMember(product_id=product.id, team_member_id=team_member.id, default_bucket_id=bucket.id, status="active"))
        db.add(
            RoadmapItem(
                source="jira_product_discovery",
                fiscal_year=2027,
                product_id=product.id,
                bucket_id=bucket.id,
                jira_issue_id="10001",
                jira_issue_key="ROADMAP-1",
                title="Student platform improvements",
                issue_type="Idea",
                source_team="Applications",
                program_area="Jira Agency Office",
            )
        )
        db.add_all(
            [
                ActualEntry(
                    product_id=product.id,
                    team_member_id=team_member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("3"),
                    source="test",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=team_member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("2"),
                    source="test",
                    source_ticket_key="SIS-1",
                    source_worklog_id="2",
                ),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=other_member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("7"),
                    source="test",
                    source_ticket_key="SIS-2",
                    source_worklog_id="3",
                ),
            ]
        )
        db.flush()

        result = team_roadmap_forecast_plan(db, "Applications", 2027, can_view_rates=False)

        assert len(result["rows"]) == 1
        assert result["rows"][0]["actual_hours"] == Decimal("5")
        assert result["rows"][0]["worklog_count"] == 2
        assert result["rows"][0]["ticket_count"] == 1
        assert result["rows"][0]["program_area"] == "Academics"
        assert result["team_members"][0]["bill_rate"] is None


def test_team_product_forecast_plan_does_not_use_roadmap_source_team_as_product_ownership():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        db.add(
            RoadmapItem(
                source="jira_product_discovery",
                fiscal_year=2027,
                product_id=product.id,
                bucket_id=bucket.id,
                jira_issue_id="10001",
                jira_issue_key="ROADMAP-1",
                title="Unassigned product work",
                issue_type="Idea",
                source_team="Applications",
            )
        )
        db.flush()

        result = team_roadmap_forecast_plan(db, "Applications", 2027)

        assert result["rows"] == []


def test_product_roadmap_items_do_not_create_noncanonical_forecast_attribution():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Core Infrastructure", slug="core-infrastructure")
        db.add(product)
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="100180",
            jira_issue_key="ROADMAP-180",
            title="TDOE Application Portfolio Annual Maintenance",
            issue_type="Idea",
        )
        db.add(roadmap_item)
        db.flush()

        rows = product_roadmap_items(db, product.id, 2027)

        assert len(rows) == 1
        assert "forecast_hours" not in rows[0]
        assert "forecast_months" not in rows[0]


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


def test_product_slugs_are_generated_and_resolve_with_numeric_fallback():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = create_product_endpoint(ProductCreate(name="Core Infrastructure"), fiscal_year=2027, db=db)
        second = create_product_endpoint(ProductCreate(name="Core Infrastructure!"), fiscal_year=2027, db=db)
        admin = local_disabled_admin()

        assert first["slug"] == "core-infrastructure"
        assert second["slug"] == "core-infrastructure-2"
        assert get_product_endpoint("core-infrastructure", fiscal_year=2027, db=db, user=admin)["id"] == first["id"]
        assert get_product_endpoint(str(first["id"]), fiscal_year=2027, db=db, user=admin)["slug"] == "core-infrastructure"


def test_team_member_slugs_are_generated_and_resolve_with_numeric_fallback():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = create_team_member_endpoint(TeamMemberCreate(name="Avery Johnson", role="Dev", team="Agency Technology"), db=db)
        second = create_team_member_endpoint(TeamMemberCreate(name="Avery Johnson!", role="QA", team="Agency Technology"), db=db)
        admin = local_disabled_admin()

        assert first["slug"] == "avery-johnson"
        assert second["slug"] == "avery-johnson-2"
        assert get_team_member_endpoint("avery-johnson", db=db, user=admin)["id"] == first["id"]
        assert get_team_member_endpoint(str(first["id"]), db=db, user=admin)["slug"] == "avery-johnson"


def test_roadmap_actual_rows_join_worklogs_without_double_counting_ambiguous_links():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month = get_fiscal_month(db, 2027, 1)
        mapped_item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
        )
        ambiguous_item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10002",
            jira_issue_key="ROADMAP-2",
            title="Ambiguous program feature",
            status="In Progress",
        )
        other_ambiguous_item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10003",
            jira_issue_key="ROADMAP-3",
            title="Second ambiguous feature",
            status="In Progress",
        )
        db.add_all([mapped_item, ambiguous_item, other_ambiguous_item])
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=mapped_item.id, jira_issue_key="SIS-1"),
                RoadmapItemIssueLink(roadmap_item_id=ambiguous_item.id, jira_issue_key="SIS-2"),
                RoadmapItemIssueLink(roadmap_item_id=other_ambiguous_item.id, jira_issue_key="SIS-2"),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("4"),
                    source="jira",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("2"),
                    source="jira",
                    source_ticket_key="SIS-2",
                    source_worklog_id="2",
                ),
            ]
        )
        db.flush()

        rows = roadmap_actual_rows(db, 2027, product_id=product.id)

        mapped = next(row for row in rows if row["mapping_status"] == "mapped")
        ambiguous = next(row for row in rows if row["mapping_status"] == "ambiguous")
        assert mapped["roadmap_item_key"] == "ROADMAP-1"
        assert mapped["actual_hours"] == 4
        assert mapped["actual_cost"] == 400
        assert mapped["ticket_keys"] == ["SIS-1"]
        assert mapped["ticket_attributions"] == [
            {
                "ticket_key": "SIS-1",
                "actual_hours": 4.0,
                "actual_cost": 400.0,
                "worklog_count": 1,
                "mapping_candidates": mapped["mapping_candidates"]["SIS-1"],
            }
        ]
        assert [candidate["jira_issue_key"] for candidate in mapped["mapping_candidates"]["SIS-1"]] == ["ROADMAP-1"]
        assert ambiguous["roadmap_item_key"] is None
        assert ambiguous["actual_hours"] == 2
        assert ambiguous["actual_cost"] == 200
        assert ambiguous["ticket_keys"] == ["SIS-2"]
        assert ambiguous["ticket_attributions"][0]["actual_hours"] == 2.0
        assert ambiguous["ticket_attributions"][0]["actual_cost"] == 200.0
        assert ambiguous["ticket_attributions"][0]["worklog_count"] == 1
        assert [candidate["jira_issue_key"] for candidate in ambiguous["mapping_candidates"]["SIS-2"]] == [
            "ROADMAP-2",
            "ROADMAP-3",
        ]


def test_roadmap_item_mapping_updates_product_and_bucket():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
        )
        db.add_all([product, item])
        db.flush()

        item.program_area = "Programs"
        mapped = update_roadmap_item_mapping(db, item.id, updates={"product_id": product.id, "bucket_id": bucket.id})
        assert mapped["product_id"] == product.id
        assert mapped["product"] == "Student Information"
        assert mapped["bucket_id"] == bucket.id
        assert mapped["bucket"] == "Maintenance"
        assert mapped["program_area"] == "Programs"
        assert mapped["product_mapping_source"] == "manual"
        assert mapped["bucket_mapping_source"] == "manual"

        cleared = update_roadmap_item_mapping(db, item.id, updates={"product_id": None, "bucket_id": None})
        assert cleared["product_id"] is None
        assert cleared["product"] is None
        assert cleared["bucket_id"] is None
        assert cleared["bucket"] is None
        assert cleared["program_area"] == "Programs"
        assert cleared["product_mapping_source"] == "sync"
        assert cleared["bucket_mapping_source"] == "sync"


def test_roadmap_issue_normalization_uses_fiscal_year_label_and_agency_office():
    issue = {
        "id": "10001",
        "key": "ROADMAP-1",
        "fields": {
            "summary": "Program billing feature",
            "labels": ["FY27", "billing"],
            "customfield_12345": {"value": "Academics"},
            "customfield_45678": {"value": "Enhancements"},
            "customfield_77777": {"value": "Product Maintenance"},
            "customfield_88888": {"start": "2026-09-01", "end": "2026-11-30"},
            "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        ["customfield_12345"],
        ["customfield_45678"],
        ["customfield_77777"],
        ["customfield_88888"],
        ["customfield_88888"],
    )

    assert _roadmap_fiscal_year_label(2027) == "FY27"
    assert _has_fiscal_year_label(payload.labels, 2027)
    assert not _has_fiscal_year_label(payload.labels, 2026)
    assert payload.issue_key == "ROADMAP-1"
    assert payload.issue_type == "Idea"
    assert payload.program_area == "Academics"
    assert payload.category == "Enhancements"
    assert payload.source_team == "Product Maintenance"
    assert payload.roadmap_start_date == date(2026, 9, 1)
    assert payload.roadmap_end_date == date(2026, 11, 30)
    assert payload.roadmap_schedule_months == (3, 4, 5)


def test_roadmap_date_field_discovery_matches_product_discovery_schedule_names():
    fields = [
        {"id": "customfield_10001", "name": "Team"},
        {"id": "customfield_10002", "name": "Delivery Start"},
        {"id": "customfield_10003", "name": "Target"},
        {"id": "customfield_10004", "name": "Roadmap Schedule"},
        {"id": "customfield_10005", "name": "Project start"},
        {"id": "customfield_10006", "name": "Project target"},
    ]

    assert _jira_date_field_ids_by_name(fields, {"start date"}, role="start") == ["customfield_10002", "customfield_10004", "customfield_10005"]
    assert _jira_date_field_ids_by_name(fields, {"target date"}, role="end") == ["customfield_10003", "customfield_10004", "customfield_10006"]
    assert _parse_jira_date({"startDate": "2026-09-01", "targetDate": "2026-11-30"}, preferred_keys=("start", "startDate", "from")) == date(2026, 9, 1)
    assert _parse_jira_date([{"startDate": "2026-09-01", "targetDate": "2026-11-30"}], preferred_keys=("target", "targetDate", "end")) == date(2026, 11, 30)
    assert _parse_jira_date({"value": "Jul-Sep, 2026"}, preferred_keys=("start",), range_position="start") == date(2026, 7, 1)
    assert _parse_jira_date({"value": "Jul-Sep, 2026"}, preferred_keys=("start",), range_position="end") == date(2026, 9, 30)


def test_roadmap_project_start_month_range_sets_schedule_months():
    issue = {
        "id": "100180",
        "key": "ROADMAP-180",
        "fields": {
            "summary": "TDOE Application Portfolio Annual Maintenance",
            "labels": ["FY27"],
            "customfield_12345": {"value": "Operations"},
            "customfield_45678": {"value": "Maintenance"},
            "customfield_77777": {"value": "Product Maintenance"},
            "customfield_99999": {"value": "Jul-Sep, 2026"},
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        ["customfield_12345"],
        ["customfield_45678"],
        ["customfield_77777"],
        ["customfield_99999"],
        [],
    )

    assert payload.roadmap_start_date == date(2026, 7, 1)
    assert payload.roadmap_end_date == date(2026, 9, 30)
    assert payload.roadmap_schedule_months == (1, 2, 3)


def test_roadmap_schedule_falls_back_to_product_discovery_month_text():
    issue = {
        "id": "100180",
        "key": "ROADMAP-180",
        "fields": {
            "summary": "TDOE Application Portfolio Annual Maintenance",
            "labels": ["FY27"],
            "created": "2026-07-02T12:00:00.000+0000",
            "customfield_99999": {"value": "Jul-Sep, 2026"},
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        [],
        [],
        [],
        [],
        [],
    )

    assert payload.roadmap_start_date == date(2026, 7, 1)
    assert payload.roadmap_end_date == date(2026, 9, 30)
    assert payload.roadmap_schedule_months == (1, 2, 3)


def test_roadmap_schedule_reads_product_discovery_rendered_field_names():
    issue = {
        "id": "100180",
        "key": "ROADMAP-180",
        "names": {
            "customfield_10005": "Project start",
            "customfield_10006": "Project target",
        },
        "fields": {
            "summary": "TDOE Application Portfolio Annual Maintenance",
            "labels": ["FY27"],
            "customfield_10005": None,
            "customfield_10006": None,
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
        "renderedFields": {
            "customfield_10005": "<span>Jul-Sep, 2026</span>",
            "customfield_10006": "<span>Oct-Dec, 2026</span>",
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        [],
        [],
        [],
        [],
        [],
    )

    assert payload.roadmap_start_date == date(2026, 7, 1)
    assert payload.roadmap_end_date == date(2026, 9, 30)
    assert payload.roadmap_schedule_months == (1, 2, 3, 4, 5, 6)


def test_roadmap_schedule_reads_product_discovery_iso_month_ranges():
    issue = {
        "id": "100180",
        "key": "ROADMAP-180",
        "names": {
            "customfield_10005": "Project start",
            "customfield_10006": "Project target",
        },
        "fields": {
            "summary": "TDOE Application Portfolio Annual Maintenance",
            "labels": ["FY27"],
            "customfield_10005": {"start": "2026-07", "end": "2026-09"},
            "customfield_10006": {"start": "2026-10", "end": "2026-12"},
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        [],
        [],
        [],
        [],
        [],
    )

    assert payload.roadmap_start_date == date(2026, 7, 1)
    assert payload.roadmap_end_date == date(2026, 9, 30)
    assert payload.roadmap_schedule_months == (1, 2, 3, 4, 5, 6)


def test_roadmap_schedule_keeps_separate_fiscal_windows():
    issue = {
        "id": "100152",
        "key": "ROADMAP-152",
        "names": {
            "customfield_10005": "Project start",
            "customfield_10006": "Project target",
        },
        "fields": {
            "summary": "Modernize the CCMS application",
            "labels": ["FY27"],
            "customfield_10005": {"value": "Jul-Sep, 2026"},
            "customfield_10006": {"value": "Jan-Mar, 2027"},
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        [],
        [],
        [],
        [],
        [],
        fiscal_year=2027,
    )

    assert payload.roadmap_schedule_months == (1, 2, 3, 7, 8, 9)


def test_roadmap_schedule_reads_fiscal_year_maintenance_span():
    issue = {
        "id": "100180",
        "key": "ROADMAP-180",
        "names": {
            "customfield_10005": "Project start",
        },
        "fields": {
            "summary": "TDOE Application Portfolio Annual Maintenance",
            "labels": ["FY27"],
            "customfield_10005": {"value": "Jul-Jun, 2027"},
            "status": {"name": "Backlog", "statusCategory": {"name": "To Do"}},
            "issuetype": {"name": "Idea"},
            "issuelinks": [],
        },
    }

    payload = _normalize_roadmap_issue(
        "https://tndoe.atlassian.net",
        issue,
        [],
        [],
        [],
        [],
        [],
        fiscal_year=2027,
    )

    assert payload.roadmap_schedule_months == tuple(range(1, 13))


def test_roadmap_category_maps_to_sparc_bucket_on_upsert():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        enhance = db.scalar(select(Bucket).where(Bucket.code == "ENHANCE"))
        payload = RoadmapIssuePayload(
            issue_id="10001",
            issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
            status_category="In Progress",
            issue_type="Idea",
            labels=("FY27",),
            program_area="Academics",
            category="Enhancements",
            source_team="Product Maintenance",
            source_url="https://tndoe.atlassian.net/browse/ROADMAP-1",
            links=tuple(),
            roadmap_start_date=date(2026, 9, 1),
            roadmap_end_date=date(2026, 11, 30),
            roadmap_schedule_months=(3, 4, 5),
        )

        item = _upsert_roadmap_item(db, payload, 2027)

        assert item.bucket_id == enhance.id
        assert item.source_category == "Enhancements"
        assert item.source_team == "Product Maintenance"
        assert item.roadmap_start_date == date(2026, 9, 1)
        assert item.roadmap_end_date == date(2026, 11, 30)
        assert item.roadmap_schedule_months == [3, 4, 5]


def test_roadmap_sync_preserves_manual_mapping_and_refreshes_jira_metadata():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        maintenance = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        payload = RoadmapIssuePayload(
            issue_id="10001",
            issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
            status_category="In Progress",
            issue_type="Idea",
            labels=("FY27",),
            program_area="Academics",
            category="Enhancements",
            source_team="Product Maintenance",
            source_url=None,
            links=tuple(),
        )
        item = _upsert_roadmap_item(db, payload, 2027)
        update_roadmap_item_mapping(db, item.id, updates={"bucket_id": maintenance.id})

        refreshed = _upsert_roadmap_item(
            db,
            RoadmapIssuePayload(
                **{**payload.__dict__, "program_area": None, "category": "Net New"},
            ),
            2027,
        )

        assert refreshed.bucket_id == maintenance.id
        assert refreshed.bucket_mapping_source == "manual"
        assert refreshed.program_area is None


def test_inactive_product_rejects_new_forecast_but_keeps_existing_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Historical Product")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        existing = upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="MAINTENANCE",
            fiscal_year=2027,
            month_sequence=1,
            hours=10,
        )
        product.is_active = False
        db.flush()

        with pytest.raises(ValueError, match="Inactive products"):
            upsert_forecast_entry(
                db,
                product_id=product.id,
                team_member_id=member.id,
                bucket_code="MAINTENANCE",
                fiscal_year=2027,
                month_sequence=2,
                hours=5,
            )

        assert db.get(ForecastEntry, existing.id).hours == Decimal("10")


def test_roadmap_sync_discovers_epic_and_story_descendants(monkeypatch: pytest.MonkeyPatch):
    payload = RoadmapIssuePayload(
        issue_id="10001",
        issue_key="ROADMAP-1",
        title="Program billing feature",
        status="In Progress",
        status_category="In Progress",
        issue_type="Idea",
        labels=("FY27",),
        program_area="Academics",
        category="Net New",
        source_team="Applications",
        source_url="https://tndoe.atlassian.net/browse/ROADMAP-1",
        links=(
            RoadmapIssueLinkPayload(
                issue_id="20010",
                issue_key="APP-10",
                issue_summary="Delivery root",
                jira_project_key="APP",
                relationship_type="Delivery",
            ),
        ),
    )
    queries: list[str] = []

    def fake_search(_client, _site_url, jql, _fields, expand=None):
        queries.append(jql)
        if jql.startswith("issuekey in"):
            return [_jira_hierarchy_issue("APP-10", "Deliverable", "Delivery root")]
        if jql == 'parent in ("APP-10")':
            return [_jira_hierarchy_issue("APP-20", "Epic", "Delivery epic", parent_key="APP-10")]
        if jql == 'parent in ("APP-20")':
            return [_jira_hierarchy_issue("APP-30", "Story", "Delivery story", parent_key="APP-20")]
        if jql == 'parent in ("APP-30")':
            return []
        raise AssertionError(f"Unexpected JQL: {jql}")

    monkeypatch.setattr("app.services.roadmap._search_jira_issues", fake_search)

    enriched = _enrich_roadmap_payload_links(object(), "https://tndoe.atlassian.net", [payload], [])

    links = {link.issue_key: link for link in enriched[0].links}
    assert list(links) == ["APP-10", "APP-20", "APP-30"]
    assert links["APP-10"].issue_type == "Deliverable"
    assert links["APP-10"].relationship_type == "Delivery"
    assert links["APP-20"].relationship_type == "Child of APP-10"
    assert links["APP-30"].relationship_type == "Child of APP-20"
    assert queries == [
        'issuekey in ("APP-10")',
        'parent in ("APP-10")',
        'parent in ("APP-20")',
        'parent in ("APP-30")',
    ]


def _jira_hierarchy_issue(key: str, issue_type: str, summary: str, *, parent_key: str | None = None) -> dict[str, object]:
    fields: dict[str, object] = {
        "summary": summary,
        "status": {"name": "In Progress", "statusCategory": {"name": "In Progress"}},
        "issuetype": {"name": issue_type},
        "project": {"key": "APP"},
    }
    if parent_key is not None:
        fields["parent"] = {"key": parent_key}
    return {"id": key.replace("APP-", "200"), "key": key, "fields": fields}


def test_stale_roadmap_items_move_out_of_selected_fiscal_year():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        stale = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Old roadmap idea",
            issue_type="Idea",
        )
        current = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10002",
            jira_issue_key="ROADMAP-2",
            title="Current roadmap idea",
            issue_type="Idea",
        )
        other_project = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10003",
            jira_issue_key="OTHER-1",
            title="Other project idea",
            issue_type="Idea",
        )
        delivery_ticket = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10004",
            jira_issue_key="ROADMAP-3",
            title="Delivery ticket",
            issue_type="Story",
        )
        db.add_all([stale, current, other_project, delivery_ticket])
        db.flush()

        removed = _remove_stale_roadmap_items_from_fiscal_year(db, 2027, "ROADMAP", {"ROADMAP-2"})

        assert removed == 1
        assert stale.fiscal_year == UNSCOPED_ROADMAP_FISCAL_YEAR
        assert current.fiscal_year == 2027
        assert other_project.fiscal_year == 2027
        assert delivery_ticket.fiscal_year == 2027


def test_product_roadmap_items_show_mapped_items_without_actuals_and_exclude_delivery_tickets():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        other_product = Product(name="Other Product", slug="other-product")
        bucket = db.scalar(select(Bucket).where(Bucket.code == "ENHANCE"))
        db.add_all([product, other_product])
        db.flush()
        idea = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
            issue_type="Idea",
            program_area="Programs",
            roadmap_start_date=date(2026, 9, 1),
            roadmap_end_date=date(2026, 11, 30),
        )
        delivery_ticket = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10002",
            jira_issue_key="ROADMAP-2",
            title="Delivery ticket that should not be a roadmap item",
            status="Done",
            issue_type="Story",
        )
        other_idea = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2026,
            product_id=other_product.id,
            bucket_id=bucket.id,
            jira_issue_id="10003",
            jira_issue_key="ROADMAP-3",
            title="Other product idea",
            issue_type="Idea",
        )
        db.add_all([idea, delivery_ticket, other_idea])
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=idea.id, jira_issue_key="SIS-1"),
                RoadmapItemIssueLink(roadmap_item_id=idea.id, jira_issue_key="SIS-2"),
                RoadmapItemIssueLink(roadmap_item_id=delivery_ticket.id, jira_issue_key="SIS-3"),
            ]
        )
        db.flush()

        rows = product_roadmap_items(db, product.id, 2027)
        prior_year_rows = product_roadmap_items(db, other_product.id, 2026)
        all_rows = list_roadmap_items(db, 2027)

        assert [row["jira_issue_key"] for row in rows] == ["ROADMAP-1"]
        assert rows[0]["linked_issue_count"] == 2
        assert rows[0]["program_area"] == "Programs"
        assert rows[0]["roadmap_start_date"] == date(2026, 9, 1)
        assert rows[0]["roadmap_end_date"] == date(2026, 11, 30)
        assert [row["jira_issue_key"] for row in prior_year_rows] == ["ROADMAP-3"]
        assert {row["jira_issue_key"] for row in all_rows} == {"ROADMAP-1"}


def test_product_roadmap_items_include_parent_ideas_through_product_deliverables():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        eceds = Product(name="ECEDS", slug="eceds")
        urs = Product(name="URS", slug="urs")
        sword = Product(name="SWORD", slug="sword")
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        db.add_all([eceds, urs, sword])
        db.flush()
        parent = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-180",
            title="TDOE Application Portfolio Annual Maintenance",
            issue_type="Idea",
            program_area="Programs",
        )
        db.add(parent)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=eceds.id,
                    bucket_id=bucket.id,
                    jira_issue_key="ECEDS-169",
                    jira_issue_summary="ECEDS continuous maintenance",
                    jira_project_key="ECEDS",
                    issue_type="Deliverable",
                    status="Not Started",
                ),
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=urs.id,
                    bucket_id=bucket.id,
                    jira_issue_key="SCREEN-470",
                    jira_issue_summary="URS SY 2026 maintenance",
                    jira_project_key="SCREEN",
                    issue_type="Deliverable",
                    status="Not Started",
                ),
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=urs.id,
                    bucket_id=bucket.id,
                    jira_issue_key="SCREEN-346",
                    jira_issue_summary="URS SY 2025 maintenance",
                    jira_project_key="SCREEN",
                    issue_type="Deliverable",
                    status="In Progress",
                ),
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=sword.id,
                    bucket_id=bucket.id,
                    jira_issue_key="SWORD-974",
                    jira_issue_summary="SWORD continuous maintenance",
                    jira_project_key="SWORD",
                    issue_type="Deliverable",
                    status="In Progress",
                ),
            ]
        )
        db.flush()

        eceds_rows = product_roadmap_items(db, eceds.id, 2027)
        urs_rows = product_roadmap_items(db, urs.id, 2027)

        assert [row["jira_issue_key"] for row in eceds_rows] == ["ROADMAP-180"]
        assert eceds_rows[0]["linked_issue_count"] == 1
        assert [link["jira_issue_key"] for link in eceds_rows[0]["linked_issues"]] == ["ECEDS-169"]
        assert [row["jira_issue_key"] for row in urs_rows] == ["ROADMAP-180"]
        assert urs_rows[0]["linked_issue_count"] == 2
        assert [link["jira_issue_key"] for link in urs_rows[0]["linked_issues"]] == ["SCREEN-346", "SCREEN-470"]


def test_story_actuals_roll_up_through_delivery_hierarchy_to_parent_idea():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="ECEDS", slug="eceds")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        month = get_fiscal_month(db, 2027, 1)
        parent = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-180",
            title="TDOE Application Portfolio Annual Maintenance",
            issue_type="Idea",
        )
        db.add(parent)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=product.id,
                    bucket_id=bucket.id,
                    jira_issue_key="ECEDS-169",
                    jira_issue_summary="ECEDS continuous maintenance",
                    jira_project_key="ECEDS",
                    issue_type="Deliverable",
                ),
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=product.id,
                    bucket_id=bucket.id,
                    jira_issue_key="ECEDS-170",
                    jira_issue_summary="ECEDS maintenance epic",
                    jira_project_key="ECEDS",
                    issue_type="Epic",
                    relationship_type="Child of ECEDS-169",
                ),
                RoadmapItemIssueLink(
                    roadmap_item_id=parent.id,
                    product_id=product.id,
                    bucket_id=bucket.id,
                    jira_issue_key="ECEDS-171",
                    jira_issue_summary="Apply maintenance update",
                    jira_project_key="ECEDS",
                    issue_type="Story",
                    relationship_type="Child of ECEDS-170",
                ),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("4"),
                    source="jira",
                    source_ticket_key="ECEDS-171",
                    source_worklog_id="1",
                ),
            ]
        )
        db.flush()

        rows = roadmap_actual_rows(db, 2027, product_id=product.id)

        assert len(rows) == 1
        assert rows[0]["mapping_status"] == "mapped"
        assert rows[0]["roadmap_item_key"] == "ROADMAP-180"
        assert rows[0]["product"] == "ECEDS"
        assert rows[0]["ticket_keys"] == ["ECEDS-171"]
        assert rows[0]["actual_hours"] == 4


def test_roadmap_actual_rows_ignore_links_to_delivery_tickets():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month = get_fiscal_month(db, 2027, 1)
        delivery_ticket = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Delivery ticket incorrectly synced as a roadmap item",
            issue_type="Story",
        )
        db.add(delivery_ticket)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=delivery_ticket.id, jira_issue_key="SIS-1"),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("4"),
                    source="jira",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
            ]
        )
        db.flush()

        rows = roadmap_actual_rows(db, 2027, product_id=product.id)

        assert len(rows) == 1
        assert rows[0]["mapping_status"] == "unmapped"
        assert rows[0]["roadmap_item_key"] is None
        assert rows[0]["actual_hours"] == 4


def test_roadmap_actual_rows_ignore_links_to_other_fiscal_year_roadmap_items():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month = get_fiscal_month(db, 2027, 1)
        prior_year_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2026,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="FY26 roadmap idea",
            issue_type="Idea",
        )
        db.add(prior_year_item)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=prior_year_item.id, jira_issue_key="SIS-1"),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("4"),
                    source="jira",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
            ]
        )
        db.flush()

        rows = roadmap_actual_rows(db, 2027, product_id=product.id)

        assert len(rows) == 1
        assert rows[0]["mapping_status"] == "unmapped"
        assert rows[0]["roadmap_item_key"] is None


def test_roadmap_actual_rows_can_filter_by_fiscal_month():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month_one = get_fiscal_month(db, 2027, 1)
        month_two = get_fiscal_month(db, 2027, 2)
        item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
        )
        db.add(item)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=item.id, jira_issue_key="SIS-1"),
                RoadmapItemIssueLink(roadmap_item_id=item.id, jira_issue_key="SIS-2"),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month_one.id,
                    hours=Decimal("4"),
                    source="jira",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month_two.id,
                    hours=Decimal("6"),
                    source="jira",
                    source_ticket_key="SIS-2",
                    source_worklog_id="2",
                ),
            ]
        )
        db.flush()

        rows = roadmap_actual_rows(db, 2027, month_sequence=1)

        assert len(rows) == 1
        assert rows[0]["actual_hours"] == 4
        assert rows[0]["ticket_keys"] == ["SIS-1"]


def test_manual_roadmap_ticket_mapping_replaces_existing_links():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="First feature",
        )
        second_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10002",
            jira_issue_key="ROADMAP-2",
            title="Second feature",
        )
        prior_year_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2026,
            jira_issue_id="10003",
            jira_issue_key="ROADMAP-0",
            title="Prior year feature",
        )
        db.add_all([first_item, second_item, prior_year_item])
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=first_item.id, jira_issue_key="SIS-1", source="jira_issue_link"),
                RoadmapItemIssueLink(roadmap_item_id=prior_year_item.id, jira_issue_key="SIS-1", source="jira_issue_link"),
            ]
        )
        db.flush()

        mapped = map_roadmap_ticket(db, "sis-1", second_item.id, fiscal_year=2027, actor=local_disabled_admin(), reason="Correction")

        links = db.scalars(select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == "SIS-1")).all()
        assert mapped["roadmap_item_key"] == "ROADMAP-2"
        assert len(links) == 2
        current_link = next(link for link in links if link.roadmap_item_id == second_item.id)
        assert current_link.source == "manual"
        assert any(link.roadmap_item_id == prior_year_item.id for link in links)
        change = db.scalar(select(AttributionChange))
        assert change is not None
        assert change.source_key == "SIS-1"
        assert change.from_value == "ROADMAP-1 - First feature"
        assert change.to_value == "ROADMAP-2 - Second feature"
        assert change.changed_by_display_name == "Local Admin"
        assert change.reason == "Correction"


def test_forecast_recommendation_apply_adds_hours_to_explicit_forecast_line():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month = get_fiscal_month(db, 2027, 1)
        item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            issue_type="Idea",
        )
        db.add(item)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=item.id, jira_issue_key="SIS-1"),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("6"),
                    source="jira",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
            ]
        )
        db.flush()

        with pytest.raises(ValueError, match="changed since this queue loaded"):
            create_forecast_recommendation_decision(
                db,
                fiscal_year=2027,
                product_id=product.id,
                bucket_id=bucket.id,
                action="applied",
                expected_forecast_hours=0,
                expected_roadmap_actual_hours=5,
                target_team_member_id=member.id,
                target_month_sequence=1,
            )
        assert db.scalar(select(ForecastEntry)) is None
        assert db.scalar(select(ForecastRecommendationDecision)) is None

        decision = create_forecast_recommendation_decision(
            db,
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            action="applied",
            expected_forecast_hours=0,
            expected_roadmap_actual_hours=6.0000000001,
            target_team_member_id=member.id,
            target_month_sequence=1,
            note="Use current roadmap actuals",
        )

        entry = db.scalar(select(ForecastEntry))
        assert entry is not None
        assert entry.product_id == product.id
        assert entry.team_member_id == member.id
        assert entry.bucket_id == bucket.id
        assert entry.fiscal_month_id == month.id
        assert entry.hours == Decimal("6.00")
        assert decision["recommendation"] == "add_forecast"
        assert decision["action"] == "applied"
        assert decision["suggested_delta_hours"] == 6
        assert decision["applied_forecast_entry_id"] == entry.id
        assert list_forecast_recommendation_decisions(db, 2027)[0]["note"] == "Use current roadmap actuals"


def test_forecast_recommendation_rejects_without_changing_forecast():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", slug="student-information")
        member = TeamMember(name="Avery Johnson", slug="avery-johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "ENHANCE"))
        month = get_fiscal_month(db, 2027, 1)
        item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            issue_type="Idea",
        )
        db.add(item)
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=item.id, jira_issue_key="SIS-1"),
                ActualEntry(
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=Decimal("4"),
                    source="jira",
                    source_ticket_key="SIS-1",
                    source_worklog_id="1",
                ),
            ]
        )
        db.flush()

        decision = create_forecast_recommendation_decision(
            db,
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            action="rejected",
            expected_forecast_hours=0,
            expected_roadmap_actual_hours=4,
            note="No forecast change needed",
        )

        assert db.scalar(select(ForecastEntry)) is None
        assert decision["recommendation"] == "add_forecast"
        assert decision["action"] == "rejected"
        assert decision["suggested_delta_hours"] == 4
        assert decision["applied_forecast_entry_id"] is None


def test_roadmap_sync_preserves_manual_ticket_links():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
        )
        db.add(item)
        db.flush()
        db.add(RoadmapItemIssueLink(roadmap_item_id=item.id, jira_issue_key="SIS-1", source="manual"))
        db.flush()

        linked = _replace_roadmap_issue_links(db, item, tuple())

        links = db.scalars(select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == "SIS-1")).all()
        assert linked == 0
        assert len(links) == 1
        assert links[0].source == "manual"


def test_roadmap_sync_does_not_recreate_a_competing_link_after_manual_remap():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        original_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Original feature",
        )
        corrected_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10002",
            jira_issue_key="ROADMAP-2",
            title="Correct feature",
        )
        db.add_all([original_item, corrected_item])
        db.flush()
        db.add_all(
            [
                RoadmapItemIssueLink(roadmap_item_id=original_item.id, jira_issue_key="SIS-1", source="jira_issue_link"),
                RoadmapItemIssueLink(roadmap_item_id=corrected_item.id, jira_issue_key="SIS-1", source="manual"),
            ]
        )
        db.flush()

        linked = _replace_roadmap_issue_links(
            db,
            original_item,
            (
                RoadmapIssueLinkPayload(
                    issue_id="20001",
                    issue_key="SIS-1",
                    issue_summary="Synced ticket",
                    jira_project_key="SIS",
                    relationship_type="Delivery",
                ),
            ),
        )

        links = db.scalars(select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == "SIS-1")).all()
        assert linked == 0
        assert len(links) == 1
        assert links[0].roadmap_item_id == corrected_item.id
        assert links[0].source == "manual"


def test_roadmap_sync_stores_product_scoped_deliverable_metadata():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="ECEDS", slug="eceds")
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        db.add(product)
        db.flush()
        db.add(ProductJiraSpace(product_id=product.id, jira_project_key="ECEDS", is_active=True))
        item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-180",
            title="TDOE Application Portfolio Annual Maintenance",
            issue_type="Idea",
        )
        db.add(item)
        db.flush()

        linked = _replace_roadmap_issue_links(
            db,
            item,
            (
                RoadmapIssueLinkPayload(
                    issue_id="20001",
                    issue_key="ECEDS-169",
                    issue_summary="ECEDS continuous maintenance",
                    jira_project_key="ECEDS",
                    relationship_type="Delivery",
                    issue_type="Deliverable",
                    status="Not Started",
                    status_category="To Do",
                    category="Maintenance",
                ),
            ),
        )

        link = db.scalar(select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == "ECEDS-169"))
        assert linked == 1
        assert link.product_id == product.id
        assert link.bucket_id == bucket.id
        assert link.issue_type == "Deliverable"
        assert link.status == "Not Started"
        assert link.status_category == "To Do"
        assert link.source_category == "Maintenance"


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


def test_dashboard_breakdowns_can_scope_to_fiscal_month():
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
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="ENHANCE",
            fiscal_year=2026,
            month_sequence=2,
            hours=20,
        )

        net_new = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month = get_fiscal_month(db, 2026, 1)
        db.add(
            ActualEntry(
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=net_new.id,
                fiscal_month_id=month.id,
                hours=Decimal("4"),
                source="test",
                source_ticket_key="SIS-1",
                source_worklog_id="1",
            )
        )
        db.flush()

        products = dashboard_products(db, 2026, month_sequence=1)
        product_row = products[0]
        net_new_totals = next(row for row in product_row["bucket_totals"] if row["bucket_code"] == "NET_NEW")
        enhance_totals = next(row for row in product_row["bucket_totals"] if row["bucket_code"] == "ENHANCE")

        assert product_row["forecasted_hours"] == 10
        assert product_row["fytd_hours"] == 4
        assert net_new_totals["forecast_hours"] == 10
        assert net_new_totals["actual_hours"] == 4
        assert enhance_totals["forecast_hours"] == 0

        work_types = dashboard_work_type_breakdown(db, 2026, month_sequence=1)
        assert next(row for row in work_types if row["bucket_code"] == "NET_NEW")["forecast_hours"] == 10
        assert next(row for row in work_types if row["bucket_code"] == "ENHANCE")["forecast_hours"] == 0

        labor_mix = dashboard_labor_mix(db, 2026, month_sequence=1)
        assert labor_mix["hire_types"][0]["forecast_hours"] == 10
        assert labor_mix["hire_types"][0]["actual_hours"] == 4


def test_dashboard_labor_mix_counts_distinct_forecast_resources_by_scope():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        first_product = Product(name="Student Information", jira_space_key="SIS")
        second_product = Product(name="Core Infrastructure", jira_space_key="CORE")
        contractor = TeamMember(
            name="Avery Johnson",
            role="Dev",
            team="Applications",
            bill_rate=Decimal("100"),
            employment_type="Contractor",
        )
        fte = TeamMember(
            name="Bailey Nguyen",
            role="QA",
            team="Applications",
            bill_rate=Decimal("80"),
            employment_type="FTE",
        )
        db.add_all([first_product, second_product, contractor, fte])
        db.flush()

        upsert_forecast_entry(
            db,
            product_id=first_product.id,
            team_member_id=contractor.id,
            bucket_code="NET_NEW",
            fiscal_year=2026,
            month_sequence=1,
            hours=10,
        )
        upsert_forecast_entry(
            db,
            product_id=second_product.id,
            team_member_id=contractor.id,
            bucket_code="ENHANCE",
            fiscal_year=2026,
            month_sequence=1,
            hours=5,
        )
        upsert_forecast_entry(
            db,
            product_id=first_product.id,
            team_member_id=fte.id,
            bucket_code="MAINTENANCE",
            fiscal_year=2026,
            month_sequence=2,
            hours=20,
        )

        july_mix = dashboard_labor_mix(db, 2026, month_sequence=1)
        fy_mix = dashboard_labor_mix(db, 2026)

        contractor_row = next(row for row in july_mix["hire_types"] if row["employment_type"] == "Contractor")
        dev_row = next(row for row in july_mix["roles"] if row["role"] == "Dev")
        fte_row = next(row for row in fy_mix["hire_types"] if row["employment_type"] == "FTE")

        assert contractor_row["forecast_hours"] == 15
        assert contractor_row["forecast_resource_count"] == 1
        assert dev_row["forecast_hours"] == 15
        assert dev_row["forecast_resource_count"] == 1
        assert fte_row["forecast_hours"] == 20
        assert fte_row["forecast_resource_count"] == 1
        assert sum(row["forecast_resource_count"] for row in fy_mix["hire_types"]) == 2


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


def test_removing_product_team_member_with_forecast_marks_assignment_inactive_and_retains_history():
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

        assert db.scalar(select(ForecastEntry)) is not None
        assert db.scalar(select(ProductTeamMember)).status == "inactive"
        assert any(bucket["rows"] for bucket in product_bucket_tables(db, product.id, 2026)["buckets"])


def test_remove_empty_forecast_line_retains_product_team_assignment():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()

        entry = upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="ENHANCE",
            fiscal_year=2026,
            month_sequence=1,
            hours=0,
        )

        assert remove_empty_forecast_line(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_id=entry.bucket_id,
            fiscal_year=2026,
        ) == 1
        assert db.scalar(select(ForecastEntry)) is None
        assert db.scalar(select(ProductTeamMember)).status == "active"


def test_remove_forecast_line_rejects_forecast_or_actual_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        product = Product(name="Student Information", jira_space_key="SIS")
        member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()

        entry = upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="ENHANCE",
            fiscal_year=2026,
            month_sequence=1,
            hours=10,
        )
        with pytest.raises(ValueError, match="Set all forecast hours to 0"):
            remove_empty_forecast_line(
                db,
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=entry.bucket_id,
                fiscal_year=2026,
            )

        entry.hours = Decimal("0")
        db.add(
            ActualEntry(
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=entry.bucket_id,
                fiscal_month_id=entry.fiscal_month_id,
                hours=Decimal("1"),
                source="test",
                source_ticket_key="SIS-1",
                source_worklog_id="1",
            )
        )
        db.flush()
        with pytest.raises(ValueError, match="Actual labor"):
            remove_empty_forecast_line(
                db,
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=entry.bucket_id,
                fiscal_year=2026,
            )


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

        moved = add_product_jira_space(db, second_product.id, jira_project_catalog_id=project.id, replace_existing=True)
        db.flush()

        assert moved.id == mapping.id
        assert list_product_jira_spaces(db, first_product.id) == []
        assert list_product_jira_spaces(db, second_product.id)[0]["jira_project_key"] == "SIS"


def test_jira_project_catalog_visibility_can_be_toggled_and_survives_refresh(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        project = JiraProjectCatalog(
            jira_project_id="10001",
            jira_project_key="IGNORE",
            jira_project_name="Ignore Me",
            project_type_key="software",
        )
        db.add(project)
        db.flush()

        updated = update_jira_project_catalog_visibility(db, project.id, False)
        assert updated["is_visible"] is False

        monkeypatch.setattr(
            jira_projects,
            "fetch_jira_projects",
            lambda: [
                JiraProjectPayload(
                    jira_project_id="10001",
                    jira_project_key="IGNORE",
                    jira_project_name="Ignore Me Updated",
                    project_type_key="software",
                )
            ],
        )
        refreshed = jira_projects.refresh_jira_project_catalog(db)
        db.flush()

        assert refreshed["projects"][0]["jira_project_name"] == "Ignore Me Updated"
        assert refreshed["projects"][0]["is_visible"] is False


def test_product_jira_space_move_and_remove_keep_legacy_mapping_aligned():
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
        legacy_mapping = JiraProductMapping(
            jira_project_key="SIS",
            jira_project_name="Student Information System",
            product_id=None,
        )
        db.add_all([first_product, second_product, project, legacy_mapping])
        db.flush()

        mapping = add_product_jira_space(db, first_product.id, jira_project_catalog_id=project.id)
        db.flush()

        assert legacy_mapping.product_id == first_product.id

        add_product_jira_space(db, second_product.id, jira_project_catalog_id=project.id, replace_existing=True)
        db.flush()

        assert legacy_mapping.product_id == second_product.id

        remove_product_jira_space(db, second_product.id, mapping.id)
        db.flush()

        assert legacy_mapping.product_id is None


def test_product_jira_space_move_reattributes_jira_actuals_and_records_impact():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _seed_buckets(db)
        source_product = Product(name="Original Product")
        target_product = Product(name="Leadership Product")
        member = TeamMember(name="Pankaj Shah", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([source_product, target_product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        month_2026 = get_fiscal_month(db, 2026, 12)
        month_2027 = get_fiscal_month(db, 2027, 1)
        space = ProductJiraSpace(product_id=source_product.id, jira_project_key="PANK", jira_project_name="Pankaj Project")
        legacy_mapping = JiraProductMapping(jira_project_key="PANK", jira_project_name="Pankaj Project", product_id=source_product.id)
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Leadership initiative",
        )
        db.add_all([space, legacy_mapping, roadmap_item])
        db.flush()
        roadmap_link = RoadmapItemIssueLink(
            roadmap_item_id=roadmap_item.id,
            product_id=source_product.id,
            jira_issue_key="PANK-1",
            jira_project_key="PANK",
        )
        jira_actuals = [
            ActualEntry(
                product_id=source_product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=month_2026.id,
                hours=Decimal("4"),
                source="jira",
                source_ticket_key="PANK-1",
                source_worklog_id="1",
                source_project_key="PANK",
            ),
            ActualEntry(
                product_id=source_product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=month_2026.id,
                hours=Decimal("2"),
                source="jira",
                source_ticket_key="PANK-OLD",
                source_worklog_id="legacy",
                source_project_key=None,
            ),
            ActualEntry(
                product_id=source_product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=month_2027.id,
                hours=Decimal("6"),
                source="mock_jira_rovo",
                source_ticket_key="PANK-2",
                source_worklog_id="2",
                source_project_key="PANK",
            ),
        ]
        manual_actual = ActualEntry(
            product_id=source_product.id,
            team_member_id=member.id,
            bucket_id=bucket.id,
            fiscal_month_id=month_2027.id,
            hours=Decimal("3"),
            source="manual",
            source_ticket_key="PANK-MANUAL",
            source_worklog_id="3",
            source_project_key="PANK",
        )
        forecast = ForecastEntry(
            product_id=source_product.id,
            team_member_id=member.id,
            bucket_id=bucket.id,
            fiscal_month_id=month_2027.id,
            hours=Decimal("20"),
        )
        db.add_all([roadmap_link, *jira_actuals, manual_actual, forecast])
        db.flush()

        result = move_product_jira_space(
            db,
            source_product.id,
            space.id,
            target_product.id,
            actor=local_disabled_admin(),
            reason="Leadership changed project ownership",
        )

        assert space.product_id == target_product.id
        assert legacy_mapping.product_id == target_product.id
        assert all(entry.product_id == target_product.id for entry in jira_actuals)
        assert manual_actual.product_id == source_product.id
        assert forecast.product_id == source_product.id
        assert roadmap_link.product_id == target_product.id
        assert result["actual_entries_moved"] == 3
        assert result["actual_hours_moved"] == 12.0
        assert result["actual_cost_moved"] == 1200.0
        assert result["roadmap_links_updated"] == 1
        change = db.scalar(select(AttributionChange))
        assert change is not None
        assert change.change_type == "jira_project_product"
        assert change.source_key == "PANK"
        assert change.from_value == "Original Product"
        assert change.to_value == "Leadership Product"
        assert change.affected_actual_count == 3
        assert change.affected_hours == Decimal("12.00")
        assert change.affected_cost == Decimal("1200.00")


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
