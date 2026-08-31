from decimal import Decimal

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import estimations as estimations_api, forecasts as forecasts_api, integrations as integrations_api, products as products_api, team_members as team_members_api, teams as teams_api
from app.db.seed import _seed_buckets
from app.models import Base, Bucket, Product, TeamMember
from app.services.access_control import AuthenticatedUser, UserRole
from app.services.aggregations import dashboard_labor_mix, dashboard_products, dashboard_summary, dashboard_work_type_breakdown, product_bucket_tables, product_summary
from app.services.auth import require_admin, require_labor_detail_access, require_role_breakdown_access, require_team_member_profile_access, require_team_page_access, require_work_type_breakdown_access
from app.services.fiscal_year import get_fiscal_month
from app.services.forecasting import upsert_forecast_entry
from app.services.reporting import build_labor_cost_report


def test_program_area_user_sees_only_assigned_dashboard_scope_without_hours():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.PROGRAM_AREA_VIEW_ONLY, ("Academics",))

        rows = dashboard_products(db, 2027, user=user)
        summary = dashboard_summary(db, 2027, user=user)
        work_types = dashboard_work_type_breakdown(db, 2027, user=user)
        labor_mix = dashboard_labor_mix(db, 2027, user=user)

    assert [row["product"] for row in rows] == ["Academics Product"]
    assert rows[0]["forecasted_cost"] == 1000
    assert rows[0]["team_members"] is None
    assert rows[0]["forecasted_hours"] is None
    assert rows[0]["fytd_hours"] is None
    assert rows[0]["remaining_hours"] is None
    assert rows[0]["variance_hours"] is None
    assert rows[0]["forecast_consumed_percent"] is None
    assert rows[0]["bucket_totals"][0]["forecast_hours"] is None
    assert rows[0]["bucket_totals"][0]["actual_hours"] is None
    assert summary["forecasted_hours"] is None
    assert summary["fytd_hours"] is None
    assert summary["team_member_count"] is None
    assert all(row["forecast_hours"] is None and row["actual_hours"] is None for row in work_types)
    assert all(row["forecast_hours"] is None and row["actual_hours"] is None for row in labor_mix["hire_types"])
    assert all(row["forecast_hours"] is None and row["actual_hours"] is None for row in labor_mix["roles"])


def test_program_area_user_cannot_request_labor_reports():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.PROGRAM_AREA_VIEW_ONLY, ("Academics",))

        with pytest.raises(PermissionError):
            build_labor_cost_report(db, 2027, dimensions=["product"], user=user)

        with pytest.raises(PermissionError):
            build_labor_cost_report(db, 2027, dimensions=["person"], user=user)


def test_program_area_product_summary_redacts_hours_but_retains_costs():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        product = _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.PROGRAM_AREA_VIEW_ONLY, ("Academics",))

        summary = product_summary(db, product.id, 2027, user=user)

    assert summary["forecasted_cost"] == 1000
    assert summary["forecasted_hours"] is None
    assert summary["fytd_hours"] is None
    assert summary["remaining_hours"] is None
    assert summary["variance_hours"] is None


def test_leadership_user_can_request_labor_reports():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.LEADERSHIP_VIEW_ONLY)

        report = build_labor_cost_report(db, 2027, dimensions=["product"], user=user)

    assert sorted(value["label"] for row in report["rows"] for value in row["dimension_values"]) == ["Academics Product", "Programs Product"]
    assert report["totals"]["forecast_cost"] == 3000


def test_leadership_dashboard_keeps_aggregate_hours_and_redacts_roster_counts():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.LEADERSHIP_VIEW_ONLY)

        rows = dashboard_products(db, 2027, user=user)
        summary = dashboard_summary(db, 2027, user=user)

    assert all(row["team_members"] is None for row in rows)
    assert summary["team_member_count"] is None
    assert summary["forecasted_hours"] == 30
    assert summary["forecasted_cost"] == 3000


def test_leadership_report_keeps_team_and_person_values_without_restricted_links():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.LEADERSHIP_VIEW_ONLY)

        report = build_labor_cost_report(db, 2027, dimensions=["person", "team", "product"], user=user)

    dimension_values = [value for row in report["rows"] for value in row["dimension_values"]]
    assert all(value["href"] is None for value in dimension_values if value["key"] in {"person", "team"})
    assert all(str(value["href"]).startswith("/products/") for value in dimension_values if value["key"] == "product")


def test_restricted_rate_viewer_gets_named_rows_without_bill_rates():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        product = _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.LEADERSHIP_VIEW_ONLY)

        tables = product_bucket_tables(db, product.id, 2027, can_view_rates=False)

    rows = [row for bucket in tables["buckets"] for row in bucket["rows"]]
    assert rows
    assert all(row["bill_rate"] is None for row in rows)
    assert {row["team_member"] for row in rows} == {"Academics Analyst"}


def test_leadership_team_forecast_plan_redacts_bill_rates():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        _seed_access_scope_data(db)
        user = _authenticated_user(UserRole.LEADERSHIP_VIEW_ONLY)

        plan = teams_api.get_team_roadmap_forecast_plan("Product", fiscal_year=2027, db=db, viewer=user)

    assert plan["team_members"]
    assert all(member["bill_rate"] is None for member in plan["team_members"])


def test_forecast_detail_route_requires_labor_detail_access():
    route = next(
        route
        for route in forecasts_api.router.routes
        if isinstance(route, APIRoute) and route.path == "/forecasts" and "GET" in route.methods
    )

    assert any(dependency.call is require_labor_detail_access for dependency in route.dependant.dependencies)


def test_team_forecast_plan_route_requires_team_page_access():
    route = next(
        route
        for route in teams_api.router.routes
        if isinstance(route, APIRoute) and route.path == "/teams/{team_ref}/roadmap-forecast-plan" and "GET" in route.methods
    )

    assert any(dependency.call is require_team_page_access for dependency in route.dependant.dependencies)


def test_jira_actual_exclusion_queue_requires_admin_access():
    route = next(
        route
        for route in integrations_api.router.routes
        if isinstance(route, APIRoute) and route.path == "/integrations/jira-rovo/worklog-exclusions" and "GET" in route.methods
    )

    assert any(dependency.call is require_admin for dependency in route.dependant.dependencies)


@pytest.mark.parametrize(
    ("path", "method", "required_dependency"),
    [
        ("/products/{product_ref}/bucket-distribution", "GET", require_work_type_breakdown_access),
        ("/products/{product_ref}/role-breakdown", "GET", require_role_breakdown_access),
        ("/products/{product_ref}/team-members", "GET", require_labor_detail_access),
        ("/products/{product_ref}/bucket-tables", "GET", require_labor_detail_access),
        ("/products/{product_ref}/roadmap-actuals", "GET", require_labor_detail_access),
    ],
)
def test_product_labor_detail_routes_require_explicit_capabilities(path, method, required_dependency):
    route = next(
        route
        for route in products_api.router.routes
        if isinstance(route, APIRoute) and route.path == path and method in route.methods
    )

    assert any(dependency.call is required_dependency for dependency in route.dependant.dependencies)


@pytest.mark.parametrize(
    ("router", "path"),
    [
        (team_members_api.router, "/team-members"),
        (estimations_api.router, "/estimations/runs"),
        (estimations_api.router, "/estimations/runs/{run_id}/allocations"),
        (estimations_api.router, "/estimations/story-point-metrics"),
        (estimations_api.router, "/estimations/delivery-flow"),
        (estimations_api.router, "/estimations/reported-values"),
    ],
)
def test_admin_labor_detail_routes_require_labor_detail_access(router, path):
    route = next(
        route
        for route in router.routes
        if isinstance(route, APIRoute) and route.path == path and "GET" in route.methods
    )

    assert any(dependency.call is require_labor_detail_access for dependency in route.dependant.dependencies)


@pytest.mark.parametrize(
    "path",
    [
        "/team-members/{team_member_ref}",
        "/team-members/{team_member_ref}/products",
        "/team-members/{team_member_ref}/actual-worklogs",
        "/team-members/{team_member_ref}/roadmap-actuals",
    ],
)
def test_team_member_profile_routes_require_profile_access(path):
    route = next(
        route
        for route in team_members_api.router.routes
        if isinstance(route, APIRoute) and route.path == path and "GET" in route.methods
    )

    assert any(dependency.call is require_team_member_profile_access for dependency in route.dependant.dependencies)


def _authenticated_user(role: UserRole, program_areas: tuple[str, ...] = ()) -> AuthenticatedUser:
    return AuthenticatedUser(
        id=1,
        email="viewer@example.org",
        display_name="Viewer",
        role=role,
        program_areas=program_areas,
    )


def _seed_access_scope_data(db: Session) -> Product:
    _seed_buckets(db)
    academics = Product(name="Academics Product", slug="academics-product", office="Academics")
    programs = Product(name="Programs Product", slug="programs-product", office="Programs")
    unassigned = Product(name="Unassigned Product", slug="unassigned-product", office=None)
    member = TeamMember(
        name="Academics Analyst",
        slug="academics-analyst",
        role="Analyst",
        team="Product",
        bill_rate=Decimal("100"),
    )
    db.add_all([academics, programs, unassigned, member])
    db.flush()

    bucket = db.query(Bucket).filter_by(code="MAINTENANCE").one()
    month = get_fiscal_month(db, 2027, 1)
    _ = month
    upsert_forecast_entry(
        db,
        product_id=academics.id,
        team_member_id=member.id,
        bucket_id=bucket.id,
        fiscal_year=2027,
        month_sequence=1,
        hours=10,
    )
    upsert_forecast_entry(
        db,
        product_id=programs.id,
        team_member_id=member.id,
        bucket_id=bucket.id,
        fiscal_year=2027,
        month_sequence=1,
        hours=20,
    )
    db.flush()
    return academics
