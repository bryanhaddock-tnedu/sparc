from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.estimations import _serialize_team_member_story_point_metrics, delivery_stage_for_status
from app.db.seed import _seed_buckets
from app.models import (
    ActualEntry,
    Base,
    Bucket,
    EstimatedEntry,
    EstimatedIssueAllocation,
    EstimationRun,
    ForecastEntry,
    JiraProductMapping,
    Product,
    TeamMember,
)
from app.services.estimation_policy import (
    EstimationIssueEvidence,
    allocate_daily_hours,
    build_issue_estimation_windows,
    complete_estimation_run,
    create_estimation_run,
    ensure_default_estimation_profile,
    persist_estimated_entries,
    preview_mock_estimation,
    reported_effective_value,
    resolve_product_mapping,
    run_mock_estimation,
    status_activity_decision,
)
from app.services.fiscal_year import ensure_fiscal_months


def test_forecast_actual_and_estimated_entries_coexist_at_same_grain():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product, member, bucket, month = _foundation(db)
        profile = ensure_default_estimation_profile(db)
        run = create_estimation_run(db, profile, 2026)
        db.add(
            ForecastEntry(
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=month.id,
                hours=Decimal("40"),
            )
        )
        db.add(
            ActualEntry(
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=month.id,
                hours=Decimal("12"),
                source_ticket_key="CCTE-1",
                source_worklog_id="wl-1",
            )
        )
        db.add(
            EstimatedEntry(
                estimation_run_id=run.id,
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=month.id,
                hours=Decimal("32"),
                method_version=run.method_version,
                confidence_score=Decimal("0.7500"),
                source_note="Unit test estimate",
            )
        )
        db.flush()

        assert db.scalar(select(ForecastEntry)).hours == Decimal("40")
        assert db.scalar(select(ActualEntry)).hours == Decimal("12")
        assert db.scalar(select(EstimatedEntry)).hours == Decimal("32")


def test_team_member_story_point_metrics_count_unique_issue_once():
    rows = [
        EstimatedIssueAllocation(
            estimation_run_id=7,
            team_member_id=10,
            issue_id="ABC1",
            issue_key="ABC-1",
            jira_project_key="ABC",
            allocated_hours=Decimal("2"),
            story_points=Decimal("5"),
            issue_logged_hours=Decimal("2"),
            included=True,
        ),
        EstimatedIssueAllocation(
            estimation_run_id=7,
            team_member_id=10,
            issue_id="ABC1",
            issue_key="ABC-1",
            jira_project_key="ABC",
            allocated_hours=Decimal("3"),
            story_points=Decimal("5"),
            issue_logged_hours=Decimal("2"),
            included=True,
        ),
        EstimatedIssueAllocation(
            estimation_run_id=7,
            team_member_id=10,
            issue_id="ABC2",
            issue_key="ABC-2",
            jira_project_key="ABC",
            allocated_hours=Decimal("4"),
            story_points=Decimal("3"),
            issue_logged_hours=Decimal("6"),
            included=True,
        ),
    ]

    metrics = _serialize_team_member_story_point_metrics(7, rows)

    assert metrics == [
        {
            "estimation_run_id": 7,
            "team_member_id": 10,
            "story_points": 8.0,
            "issue_logged_hours": 8.0,
            "story_points_per_logged_hour": 1.0,
            "issue_count": 2,
        }
    ]


def test_delivery_stage_taxonomy_separates_engineering_done_from_uat():
    assert delivery_stage_for_status("Ready for UAT", "In Progress") == "engineering_work_done"
    assert delivery_stage_for_status("Dev Complete", "In Progress") == "engineering_work_done"
    assert delivery_stage_for_status("In UAT", "In Progress") == "business_acceptance"
    assert delivery_stage_for_status("Awaiting Business Acceptance", "In Progress") == "business_acceptance"
    assert delivery_stage_for_status("UAT Complete", "Done") == "done"
    assert delivery_stage_for_status("Done", "Done") == "done"
    assert delivery_stage_for_status("In Development", "In Progress") == "in_engineering"


def test_reported_effective_rule_uses_actual_for_closed_months_when_complete_or_unestimated():
    actual_complete = reported_effective_value(
        forecast_hours=Decimal("100"),
        actual_hours=Decimal("80"),
        estimated_hours=Decimal("100"),
        month_closed=True,
        future_or_planning_month=False,
    )
    incomplete_actual = reported_effective_value(
        forecast_hours=Decimal("100"),
        actual_hours=Decimal("40"),
        estimated_hours=Decimal("100"),
        month_closed=True,
        future_or_planning_month=False,
    )
    future_forecast = reported_effective_value(
        forecast_hours=Decimal("72"),
        actual_hours=Decimal("0"),
        estimated_hours=Decimal("0"),
        month_closed=False,
        future_or_planning_month=True,
    )
    actual_without_estimate = reported_effective_value(
        forecast_hours=Decimal("100"),
        actual_hours=Decimal("22"),
        estimated_hours=Decimal("0"),
        month_closed=True,
        future_or_planning_month=False,
    )

    assert actual_complete.source == "actual"
    assert actual_complete.hours == Decimal("80")
    assert incomplete_actual.source == "estimated"
    assert incomplete_actual.hours == Decimal("100")
    assert future_forecast.source == "forecast"
    assert future_forecast.hours == Decimal("72")
    assert actual_without_estimate.source == "actual"
    assert actual_without_estimate.hours == Decimal("22")


def test_status_policy_excludes_no_activity_statuses():
    assert not status_activity_decision("On Hold", "In Progress", Decimal("0")).included
    assert not status_activity_decision("Blocked", "In Progress", Decimal("0")).included
    assert not status_activity_decision("Cancelled", "Done", Decimal("0")).included
    assert not status_activity_decision("Ready for Development", "To Do", Decimal("0")).included
    assert status_activity_decision("Ready for Development", "To Do", Decimal("3")).included


def test_overlapping_tickets_do_not_exceed_daily_person_capacity():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _product, member, _bucket, _month = _foundation(db)
        profile = ensure_default_estimation_profile(db)
        issues = [
            _issue(member.id, "CCTE-1", created=datetime(2026, 5, 1, 9), updated=datetime(2026, 5, 1, 10)),
            _issue(member.id, "CCTE-2", created=datetime(2026, 5, 1, 9), updated=datetime(2026, 5, 1, 11)),
        ]

        windows = build_issue_estimation_windows(db, profile, 2026, issues)
        allocations = allocate_daily_hours(windows, monthly_capacity_hours=profile.monthly_capacity_hours)

        assert len(allocations) == 2
        assert sum((allocation.allocated_hours for allocation in allocations), Decimal("0")) == allocations[0].day_capacity_hours


def test_unknown_jira_projects_are_unmapped_not_core_infrastructure():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Product(name="Core Infrastructure"))
        db.flush()

        unknown = resolve_product_mapping(db, "ZZZ", "Mystery Project")
        excluded = resolve_product_mapping(db, "ROADMAP", "Roadmap")
        core = resolve_product_mapping(db, "GOV", "Governance")
        saved_reference = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == "ZZZ"))

        assert unknown.status == "unmapped"
        assert unknown.product_id is None
        assert saved_reference is not None
        assert saved_reference.product_id is None
        assert excluded.status == "excluded"
        assert core.status == "mapped"
        assert core.product_name == "Core Infrastructure"


def test_excluded_jira_projects_generate_no_counted_estimate():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _product, member, _bucket, _month = _foundation(db)
        profile = ensure_default_estimation_profile(db)

        windows = build_issue_estimation_windows(
            db,
            profile,
            2026,
            [_issue(member.id, "ROADMAP-1", project_key="ROADMAP", created=datetime(2026, 5, 1), updated=datetime(2026, 5, 1))],
        )
        allocations = allocate_daily_hours(windows, monthly_capacity_hours=profile.monthly_capacity_hours)

        assert windows[0].included is False
        assert windows[0].exclusion_reason == "Excluded due to project policy"
        assert allocations == []


def test_project_pause_dates_cut_off_estimates():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _product, member, _bucket, _month = _foundation(db)
        profile = ensure_default_estimation_profile(db)
        profile.project_pause_dates = '{"CCTE": "2026-05-04"}'
        issue = _issue(member.id, "CCTE-1", created=datetime(2026, 5, 1), updated=datetime(2026, 5, 10))

        windows = build_issue_estimation_windows(db, profile, 2026, [issue])
        allocations = allocate_daily_hours(windows, monthly_capacity_hours=profile.monthly_capacity_hours)

        assert windows[0].active_end == date(2026, 5, 3)
        assert allocations
        assert all(allocation.allocation_date < date(2026, 5, 4) for allocation in allocations)


def test_estimation_runs_snapshot_rules_and_preserve_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        product, member, bucket, month = _foundation(db)
        profile = ensure_default_estimation_profile(db)
        first_run = create_estimation_run(db, profile, 2026)
        second_run = create_estimation_run(db, profile, 2026)
        for run, hours in [(first_run, Decimal("20")), (second_run, Decimal("25"))]:
            db.add(
                EstimatedEntry(
                    estimation_run_id=run.id,
                    product_id=product.id,
                    team_member_id=member.id,
                    bucket_id=bucket.id,
                    fiscal_month_id=month.id,
                    hours=hours,
                    method_version=run.method_version,
                    confidence_score=Decimal("0.7500"),
                )
            )
            complete_estimation_run(db, run, imported_issue_count=1, estimated_entry_count=1)
        db.flush()

        runs = db.scalars(select(EstimationRun).order_by(EstimationRun.id)).all()
        estimates = db.scalars(select(EstimatedEntry).order_by(EstimatedEntry.estimation_run_id)).all()
        assert all(run.method_version == "annual-hourly-report-v1" for run in runs)
        assert all("actual_completeness_threshold" in run.rules_snapshot for run in runs)
        assert [estimate.hours for estimate in estimates] == [Decimal("20"), Decimal("25")]


def test_persist_estimated_entries_groups_daily_allocations_by_month_grain():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _product, member, _bucket, _month = _foundation(db)
        profile = ensure_default_estimation_profile(db)
        run = create_estimation_run(db, profile, 2026)
        issues = [_issue(member.id, "CCTE-1", created=datetime(2026, 5, 1), updated=datetime(2026, 5, 1))]
        windows = build_issue_estimation_windows(db, profile, 2026, issues)
        allocations = allocate_daily_hours(windows, monthly_capacity_hours=profile.monthly_capacity_hours)

        entries = persist_estimated_entries(db, run, allocations)

        assert len(entries) == 1
        assert entries[0].hours > 0
        assert run.estimated_entry_count == 1


def test_preview_mock_estimation_does_not_create_run_history():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _policy_foundation(db)

        summary = preview_mock_estimation(db, 2026)

        assert summary.imported_issue_count == 10
        assert summary.run_id is None
        assert summary.estimated_entry_count > 0
        assert db.scalar(select(EstimationRun)) is None
        assert db.scalar(select(EstimatedEntry)) is None
        assert db.scalar(select(EstimatedIssueAllocation)) is None


def test_run_mock_estimation_persists_entries_audit_and_unmapped_references():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        _policy_foundation(db)

        summary = run_mock_estimation(db, 2026)

        run = db.get(EstimationRun, summary.run_id)
        assert run is not None
        assert run.status == "completed"
        assert summary.imported_issue_count == 10
        assert summary.included_issue_count > 0
        assert summary.excluded_issue_count > 0
        assert db.scalars(select(EstimatedEntry)).all()
        audit_rows = db.scalars(select(EstimatedIssueAllocation)).all()
        assert audit_rows
        assert any(row.included and row.allocated_hours > 0 for row in audit_rows)
        assert any(row.exclusion_reason == "Unmapped Jira project" for row in audit_rows)
        assert any(row.exclusion_reason == "Excluded due to project policy" for row in audit_rows)
        unknown = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == "ZZZ"))
        assert unknown is not None
        assert unknown.product_id is None


def _foundation(db: Session):
    _seed_buckets(db)
    months = ensure_fiscal_months(db, 2026)
    product = Product(name="CCTE", budget_amount=Decimal("1000.00"))
    member = TeamMember(name="Avery Johnson", role="Engineer", team="Applications", bill_rate=Decimal("100"))
    db.add_all([product, member])
    db.flush()
    bucket = db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
    month = next(month for month in months if month.sequence == 11)
    return product, member, bucket, month


def _policy_foundation(db: Session):
    _seed_buckets(db)
    ensure_fiscal_months(db, 2026)
    for name in ["CCTE", "TISA", "RC", "Core Infrastructure"]:
        db.add(Product(name=name, budget_amount=Decimal("1000.00")))
    for index, name in enumerate(["Avery Johnson", "Morgan Lee", "Sam Patel", "Riley Chen", "Jordan Smith"], start=1):
        db.add(
            TeamMember(
                staff_id=f"TEST-{index}",
                name=name,
                role="Engineer",
                team="Applications",
                bill_rate=Decimal("100"),
            )
        )
    db.flush()
    ensure_default_estimation_profile(db)


def _issue(
    member_id: int,
    issue_key: str,
    *,
    project_key: str = "CCTE",
    created: datetime,
    updated: datetime,
):
    return EstimationIssueEvidence(
        team_member_id=member_id,
        issue_id=issue_key.replace("-", ""),
        issue_key=issue_key,
        issue_summary="Estimate test issue",
        jira_project_key=project_key,
        jira_project_name=project_key,
        issue_status="In Progress",
        status_category="In Progress",
        issue_type="Task",
        story_points=Decimal("3"),
        issue_logged_hours=Decimal("0"),
        created_at_from_jira=created,
        updated_at_from_jira=updated,
        source_work_type="Net New",
    )
