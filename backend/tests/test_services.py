from decimal import Decimal

import pytest
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
    Base,
    Bucket,
    ForecastEntry,
    JiraProductMapping,
    JiraProjectCatalog,
    Product,
    ProductBudget,
    ProductTeamMember,
    RoadmapItem,
    RoadmapItemIssueLink,
    TeamMember,
)
from app.schemas import ProductCreate, TeamMemberCreate
from app.services.aggregations import dashboard_labor_mix, dashboard_products, dashboard_work_type_breakdown, product_bucket_tables, product_summary
from app.services.costs import calculate_cost
from app.services.fiscal_year import fiscal_sequence_for_date, fiscal_year_for_date, get_fiscal_month
from app.services.forecasting import upsert_forecast_entry
from app.services.jira_projects import (
    JiraProjectPayload,
    add_product_jira_space,
    list_product_jira_spaces,
    remove_product_jira_space,
    update_jira_project_catalog_visibility,
    update_product_jira_space,
)
from app.services import jira_projects
from app.services.roadmap import (
    _replace_roadmap_issue_links,
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


def test_product_slugs_are_generated_and_resolve_with_numeric_fallback():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = create_product_endpoint(ProductCreate(name="Core Infrastructure"), fiscal_year=2027, db=db)
        second = create_product_endpoint(ProductCreate(name="Core Infrastructure!"), fiscal_year=2027, db=db)

        assert first["slug"] == "core-infrastructure"
        assert second["slug"] == "core-infrastructure-2"
        assert get_product_endpoint("core-infrastructure", fiscal_year=2027, db=db)["id"] == first["id"]
        assert get_product_endpoint(str(first["id"]), fiscal_year=2027, db=db)["slug"] == "core-infrastructure"


def test_team_member_slugs_are_generated_and_resolve_with_numeric_fallback():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = create_team_member_endpoint(TeamMemberCreate(name="Avery Johnson", role="Dev", team="Agency Technology"), db=db)
        second = create_team_member_endpoint(TeamMemberCreate(name="Avery Johnson!", role="QA", team="Agency Technology"), db=db)

        assert first["slug"] == "avery-johnson"
        assert second["slug"] == "avery-johnson-2"
        assert get_team_member_endpoint("avery-johnson", db=db)["id"] == first["id"]
        assert get_team_member_endpoint(str(first["id"]), db=db)["slug"] == "avery-johnson"


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
        assert ambiguous["roadmap_item_key"] is None
        assert ambiguous["actual_hours"] == 2
        assert ambiguous["actual_cost"] == 200
        assert ambiguous["ticket_keys"] == ["SIS-2"]


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

        mapped = update_roadmap_item_mapping(db, item.id, product_id=product.id, bucket_id=bucket.id, program_area="Programs")
        assert mapped["product_id"] == product.id
        assert mapped["product"] == "Student Information"
        assert mapped["bucket_id"] == bucket.id
        assert mapped["bucket"] == "Maintenance"
        assert mapped["program_area"] == "Programs"

        cleared = update_roadmap_item_mapping(db, item.id, product_id=None, bucket_id=None)
        assert cleared["product_id"] is None
        assert cleared["product"] is None
        assert cleared["bucket_id"] is None
        assert cleared["bucket"] is None
        assert cleared["program_area"] is None


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
            product_id=product.id,
            bucket_id=bucket.id,
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="Program billing feature",
            status="In Progress",
            issue_type="Idea",
            program_area="Programs",
        )
        delivery_ticket = RoadmapItem(
            source="jira_product_discovery",
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

        rows = product_roadmap_items(db, product.id)
        all_rows = list_roadmap_items(db)

        assert [row["jira_issue_key"] for row in rows] == ["ROADMAP-1"]
        assert rows[0]["linked_issue_count"] == 2
        assert rows[0]["program_area"] == "Programs"
        assert {row["jira_issue_key"] for row in all_rows} == {"ROADMAP-1", "ROADMAP-3"}


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
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="First feature",
        )
        second_item = RoadmapItem(
            source="jira_product_discovery",
            jira_issue_id="10002",
            jira_issue_key="ROADMAP-2",
            title="Second feature",
        )
        db.add_all([first_item, second_item])
        db.flush()
        db.add(RoadmapItemIssueLink(roadmap_item_id=first_item.id, jira_issue_key="SIS-1", source="jira_issue_link"))
        db.flush()

        mapped = map_roadmap_ticket(db, "sis-1", second_item.id)

        links = db.scalars(select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == "SIS-1")).all()
        assert mapped["roadmap_item_key"] == "ROADMAP-2"
        assert len(links) == 1
        assert links[0].roadmap_item_id == second_item.id
        assert links[0].source == "manual"


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
