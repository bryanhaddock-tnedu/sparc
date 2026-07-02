from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import calendar
import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActualEntry,
    Bucket,
    EstimatedEntry,
    EstimatedIssueAllocation,
    EstimationProfile,
    EstimationRun,
    FiscalMonth,
    ForecastEntry,
    JiraProductMapping,
    Product,
    ProductJiraSpace,
    TeamMember,
)
from app.models.entities import utcnow
from app.services.fiscal_year import ensure_fiscal_months, fiscal_sequence_for_date
from app.services.slugs import product_url_slug, team_member_url_slug

METHOD_VERSION = "annual-hourly-report-v1"
DEFAULT_MONTHLY_CAPACITY_HOURS = Decimal("120.00")
DEFAULT_ACTUAL_COMPLETENESS_THRESHOLD = Decimal("0.7500")
DEFAULT_STALE_TICKET_WINDOW_DAYS = 10
DEFAULT_FUTURE_MONTH_AVERAGE_WINDOW = 2

EXPLICIT_PROJECT_PRODUCT_MAP = {
    "CCTE": "CCTE",
    "TISA": "TISA",
    "RC": "RC",
    "GOV": "Core Infrastructure",
    "RPA": "Core Infrastructure",
}

EXCLUDED_PROJECT_KEYS = {
    "APPDEV",
    "ATO",
    "CIS",
    "DYNINTAKE",
    "HB",
    "PRJ",
    "QA",
    "ROADMAP",
    "UI",
}

EXCLUDED_STATUSES = {"onhold", "blocked", "cancelled", "canceled"}
LOW_ACTIVITY_STATUSES = {"notstarted", "todo", "readyfordevelopment"}

WORK_TYPE_FIELD_PRIORITY = (
    "Work Type",
    "Type of Work",
    "Work Category",
    "Development Type",
    "Request Type",
)

WORK_TYPE_ALIASES = {
    "netnew": "NET_NEW",
    "new": "NET_NEW",
    "newfeature": "NET_NEW",
    "newdevelopment": "NET_NEW",
    "enhance": "ENHANCE",
    "enhancement": "ENHANCE",
    "enhanceexisting": "ENHANCE",
    "maintenance": "MAINTENANCE",
    "maintain": "MAINTENANCE",
    "support": "MAINTENANCE",
    "bugfix": "MAINTENANCE",
}

ISSUE_TYPE_DEFAULT_HOURS = {
    "Story": Decimal("8.0"),
    "Bug": Decimal("5.0"),
    "Task": Decimal("4.5"),
    "Spike": Decimal("6.0"),
    "Routine Task": Decimal("3.5"),
    "Normal": Decimal("3.5"),
    "Sub-task": Decimal("2.0"),
    "Epic": Decimal("12.0"),
    "Notification": Decimal("1.0"),
}

ISSUE_TYPE_POINT_MULTIPLIER = {
    "Story": Decimal("1.0"),
    "Bug": Decimal("0.85"),
    "Task": Decimal("0.8"),
    "Spike": Decimal("0.9"),
    "Routine Task": Decimal("0.7"),
    "Normal": Decimal("0.7"),
    "Sub-task": Decimal("0.45"),
    "Epic": Decimal("1.25"),
    "Notification": Decimal("0.25"),
}


@dataclass(frozen=True)
class ProductMappingDecision:
    jira_project_key: str
    product_id: int | None
    product_name: str | None
    status: str
    reason: str

    @property
    def is_counted(self) -> bool:
        return self.product_id is not None and self.status == "mapped"


@dataclass(frozen=True)
class BucketDecision:
    bucket_code: str
    bucket_id: int | None
    source_value: str
    reason: str
    defaulted: bool


@dataclass(frozen=True)
class StatusDecision:
    included: bool
    coverage_weight: Decimal
    reason: str


@dataclass(frozen=True)
class EstimationIssueEvidence:
    team_member_id: int
    issue_id: str
    issue_key: str
    issue_summary: str
    jira_project_key: str
    jira_project_name: str = ""
    issue_status: str = ""
    status_category: str = ""
    issue_type: str = "Task"
    story_points: Decimal = Decimal("0")
    issue_logged_hours: Decimal = Decimal("0")
    created_at_from_jira: datetime | None = None
    updated_at_from_jira: datetime | None = None
    resolved_at_from_jira: datetime | None = None
    source_work_type: str = ""


@dataclass(frozen=True)
class IssueEstimationWindow:
    evidence: EstimationIssueEvidence
    product_mapping: ProductMappingDecision
    bucket: BucketDecision
    included: bool
    inclusion_reason: str | None
    exclusion_reason: str | None
    active_start: date | None
    active_end: date | None
    effort_weight: Decimal
    coverage_weight: Decimal


@dataclass(frozen=True)
class DailyIssueAllocation:
    issue_key: str
    team_member_id: int
    product_id: int
    bucket_id: int
    allocation_date: date
    allocated_hours: Decimal
    day_capacity_hours: Decimal
    active_ticket_count: int


@dataclass(frozen=True)
class ReportedValueDecision:
    hours: Decimal
    source: str
    reason: str


@dataclass(frozen=True)
class EstimationRunSummary:
    fiscal_year: int
    profile_id: int
    method_version: str
    imported_issue_count: int
    included_issue_count: int
    excluded_issue_count: int
    unmapped_issue_count: int
    estimated_entry_count: int
    estimated_hours: Decimal
    warning_count: int
    warnings: list[str]
    run_id: int | None = None
    status: str = "preview"


def ensure_default_estimation_profile(db: Session) -> EstimationProfile:
    profile = db.scalar(select(EstimationProfile).where(EstimationProfile.name == "Default estimation policy"))
    if profile is not None:
        return profile

    profile = EstimationProfile(
        name="Default estimation policy",
        description="Migrated from Annual Hourly Report Jira TimeTracking estimator rules.",
        is_active=True,
        method_version=METHOD_VERSION,
        monthly_capacity_hours=DEFAULT_MONTHLY_CAPACITY_HOURS,
        actual_completeness_threshold=DEFAULT_ACTUAL_COMPLETENESS_THRESHOLD,
        stale_ticket_window_days=DEFAULT_STALE_TICKET_WINDOW_DAYS,
        forecast_future_months=True,
        future_month_average_window=DEFAULT_FUTURE_MONTH_AVERAGE_WINDOW,
        excluded_statuses=json.dumps(sorted(EXCLUDED_STATUSES)),
        low_activity_statuses=json.dumps(sorted(LOW_ACTIVITY_STATUSES)),
        excluded_jira_project_keys=json.dumps(sorted(EXCLUDED_PROJECT_KEYS)),
        project_pause_dates=json.dumps({}),
        work_type_field_priority=json.dumps(list(WORK_TYPE_FIELD_PRIORITY)),
        story_point_weighting_enabled=True,
        notes="Unknown Jira project keys stay unmapped for review; they are not assigned to Core Infrastructure.",
    )
    db.add(profile)
    db.flush()
    return profile


def profile_rules_snapshot(profile: EstimationProfile) -> str:
    payload = {
        "method_version": profile.method_version,
        "monthly_capacity_hours": str(profile.monthly_capacity_hours),
        "actual_completeness_threshold": str(profile.actual_completeness_threshold),
        "stale_ticket_window_days": profile.stale_ticket_window_days,
        "forecast_future_months": profile.forecast_future_months,
        "future_month_average_window": profile.future_month_average_window,
        "excluded_statuses": _loads_list(profile.excluded_statuses),
        "low_activity_statuses": _loads_list(profile.low_activity_statuses),
        "excluded_jira_project_keys": _loads_list(profile.excluded_jira_project_keys),
        "project_pause_dates": _loads_dict(profile.project_pause_dates),
        "work_type_field_priority": _loads_list(profile.work_type_field_priority),
        "story_point_weighting_enabled": profile.story_point_weighting_enabled,
    }
    return json.dumps(payload, sort_keys=True)


def create_estimation_run(
    db: Session,
    profile: EstimationProfile,
    fiscal_year: int,
    *,
    source_jira_updated_from: datetime | None = None,
    source_jira_updated_to: datetime | None = None,
) -> EstimationRun:
    run = EstimationRun(
        profile_id=profile.id,
        method_version=profile.method_version,
        rules_snapshot=profile_rules_snapshot(profile),
        fiscal_year=fiscal_year,
        source_jira_updated_from=source_jira_updated_from,
        source_jira_updated_to=source_jira_updated_to,
        status="running",
    )
    db.add(run)
    db.flush()
    return run


def complete_estimation_run(
    db: Session,
    run: EstimationRun,
    *,
    imported_issue_count: int,
    estimated_entry_count: int,
    warning_count: int = 0,
    status: str = "completed",
    error_summary: str | None = None,
) -> EstimationRun:
    run.status = status
    run.imported_issue_count = imported_issue_count
    run.estimated_entry_count = estimated_entry_count
    run.warning_count = warning_count
    run.error_summary = error_summary
    run.completed_at = utcnow()
    db.flush()
    return run


def resolve_product_mapping(
    db: Session,
    jira_project_key: str,
    jira_project_name: str = "",
    *,
    record_unmapped: bool = True,
) -> ProductMappingDecision:
    key = clean(jira_project_key).upper()
    if key in EXCLUDED_PROJECT_KEYS:
        return ProductMappingDecision(key, None, None, "excluded", "Excluded by Jira project policy")

    explicit_product_name = EXPLICIT_PROJECT_PRODUCT_MAP.get(key)
    if explicit_product_name:
        product = db.scalar(select(Product).where(Product.name == explicit_product_name))
        if product is not None:
            return ProductMappingDecision(key, product.id, product.name, "mapped", "Explicit Jira project policy")
        return ProductMappingDecision(key, None, explicit_product_name, "unmapped", "Configured product does not exist")

    product_space = db.scalar(
        select(ProductJiraSpace)
        .where(
            ProductJiraSpace.jira_project_key == key,
            ProductJiraSpace.is_active.is_(True),
        )
    )
    if product_space is not None and product_space.product_id is not None:
        return ProductMappingDecision(
            key,
            product_space.product_id,
            product_space.product.name if product_space.product else None,
            "mapped",
            "Product Jira space mapping",
        )

    legacy_mapping = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == key))
    if legacy_mapping is not None and legacy_mapping.product_id is not None:
        return ProductMappingDecision(
            key,
            legacy_mapping.product_id,
            legacy_mapping.product.name if legacy_mapping.product else None,
            "mapped",
            "Legacy Jira product mapping",
        )

    if record_unmapped:
        _ensure_unmapped_product_reference(db, key, jira_project_name)
    return ProductMappingDecision(key, None, None, "unmapped", "Unmapped Jira project requires review")


def normalize_bucket(db: Session, raw_work_type: str) -> BucketDecision:
    source_value = clean(raw_work_type)
    bucket_code = WORK_TYPE_ALIASES.get(normalize_lookup_value(source_value), "MAINTENANCE")
    bucket = db.scalar(select(Bucket).where(Bucket.code == bucket_code))
    defaulted = bucket_code == "MAINTENANCE" and normalize_lookup_value(source_value) not in WORK_TYPE_ALIASES
    reason = "Defaulted to Maintenance" if defaulted else "Matched Jira work type"
    return BucketDecision(bucket_code, bucket.id if bucket else None, source_value, reason, defaulted)


def status_activity_decision(
    status: str,
    status_category: str,
    logged_hours: Decimal | float | int,
    profile: EstimationProfile | None = None,
) -> StatusDecision:
    logged = Decimal(str(logged_hours or 0))
    excluded_statuses = {normalize_lookup_value(item) for item in _loads_list(profile.excluded_statuses)} if profile else EXCLUDED_STATUSES
    low_activity_statuses = {normalize_lookup_value(item) for item in _loads_list(profile.low_activity_statuses)} if profile else LOW_ACTIVITY_STATUSES
    normalized_status = normalize_lookup_value(status)

    if normalized_status in excluded_statuses:
        return StatusDecision(False, Decimal("0"), "Excluded due to status")
    if normalized_status in low_activity_statuses and logged <= 0:
        return StatusDecision(False, Decimal("0"), "Excluded due to low-activity status without logged time")
    if clean(status_category).casefold() == "to do" and logged <= 0:
        return StatusDecision(False, Decimal("0"), "Excluded due to To Do status category without logged time")
    return StatusDecision(True, Decimal("1"), "Included due to Jira activity/status")


def issue_active_window(
    created: datetime | None,
    updated: datetime | None,
    resolved: datetime | None,
    fiscal_start: date,
    fiscal_end: date,
    stale_window_days: int = DEFAULT_STALE_TICKET_WINDOW_DAYS,
) -> tuple[date, date] | None:
    if created is None:
        return None
    end_dt = resolved or updated or created
    if end_dt < created:
        end_dt = created
    start_date = created.date()
    end_date = end_dt.date()
    if (end_date - start_date).days + 1 > stale_window_days:
        start_date = end_date - timedelta(days=stale_window_days - 1)
    start_date = max(start_date, fiscal_start)
    end_date = min(end_date, fiscal_end)
    if end_date < start_date:
        return None
    return start_date, end_date


def apply_project_pause_date(window: tuple[date, date], pause_date: date | None) -> tuple[date, date] | None:
    if pause_date is None:
        return window
    start_date, end_date = window
    end_date = min(end_date, pause_date - timedelta(days=1))
    if end_date < start_date:
        return None
    return start_date, end_date


def effort_weight(
    issue_type: str,
    story_points: Decimal | float | int,
    logged_hours: Decimal | float | int,
    *,
    story_point_weighting_enabled: bool = True,
) -> Decimal:
    default_hours = ISSUE_TYPE_DEFAULT_HOURS.get(clean(issue_type), Decimal("4.0"))
    estimated = default_hours
    points = Decimal(str(story_points or 0))
    logged = Decimal(str(logged_hours or 0))
    if story_point_weighting_enabled and points > 0:
        multiplier = ISSUE_TYPE_POINT_MULTIPLIER.get(clean(issue_type), Decimal("0.8"))
        estimated = max(default_hours, points * Decimal("4.0") * multiplier)
    if logged > 0:
        estimated = max(estimated, logged)
    return min(max(estimated, Decimal("0.5")), Decimal("32.0"))


def build_issue_estimation_windows(
    db: Session,
    profile: EstimationProfile,
    fiscal_year: int,
    issues: list[EstimationIssueEvidence],
) -> list[IssueEstimationWindow]:
    fiscal_start = date(fiscal_year - 1, 7, 1)
    fiscal_end = date(fiscal_year, 6, 30)
    pause_dates = _project_pause_dates(profile)
    windows: list[IssueEstimationWindow] = []

    for issue in issues:
        mapping = resolve_product_mapping(db, issue.jira_project_key, issue.jira_project_name)
        bucket = normalize_bucket(db, issue.source_work_type)
        status = status_activity_decision(issue.issue_status, issue.status_category, issue.issue_logged_hours, profile)
        effort = effort_weight(
            issue.issue_type,
            issue.story_points,
            issue.issue_logged_hours,
            story_point_weighting_enabled=profile.story_point_weighting_enabled,
        )

        if mapping.status == "excluded":
            windows.append(_excluded_window(issue, mapping, bucket, "Excluded due to project policy", effort))
            continue
        if mapping.status == "unmapped":
            windows.append(_excluded_window(issue, mapping, bucket, "Unmapped Jira project", effort))
            continue
        if bucket.bucket_id is None:
            windows.append(_excluded_window(issue, mapping, bucket, "No matching SPARC bucket", effort))
            continue
        if not status.included:
            windows.append(_excluded_window(issue, mapping, bucket, status.reason, effort))
            continue

        active = issue_active_window(
            issue.created_at_from_jira,
            issue.updated_at_from_jira,
            issue.resolved_at_from_jira,
            fiscal_start,
            fiscal_end,
            stale_window_days=profile.stale_ticket_window_days,
        )
        if active is None:
            windows.append(_excluded_window(issue, mapping, bucket, "No active window inside fiscal year", effort))
            continue
        paused = apply_project_pause_date(active, pause_dates.get(mapping.jira_project_key))
        if paused is None:
            windows.append(_excluded_window(issue, mapping, bucket, "Excluded due to project pause date", effort))
            continue

        windows.append(
            IssueEstimationWindow(
                evidence=issue,
                product_mapping=mapping,
                bucket=bucket,
                included=True,
                inclusion_reason="Included by estimation policy",
                exclusion_reason=None,
                active_start=paused[0],
                active_end=paused[1],
                effort_weight=effort,
                coverage_weight=status.coverage_weight,
            )
        )
    return windows


def allocate_daily_hours(
    windows: list[IssueEstimationWindow],
    *,
    monthly_capacity_hours: Decimal | float | int = DEFAULT_MONTHLY_CAPACITY_HOURS,
) -> list[DailyIssueAllocation]:
    capacity = Decimal(str(monthly_capacity_hours))
    windows_by_person_day: dict[tuple[int, date], list[IssueEstimationWindow]] = defaultdict(list)
    for window in windows:
        if not window.included or window.active_start is None or window.active_end is None:
            continue
        for day in iter_business_days(window.active_start, window.active_end):
            windows_by_person_day[(window.evidence.team_member_id, day)].append(window)

    allocations: list[DailyIssueAllocation] = []
    for (_team_member_id, day), day_windows in sorted(windows_by_person_day.items(), key=lambda item: item[0]):
        daily_capacity = capacity / Decimal(str(business_days_in_month(date(day.year, day.month, 1))))
        coverage = max(window.coverage_weight for window in day_windows)
        estimated_day_hours = daily_capacity * coverage
        weights = [window.effort_weight * window.coverage_weight for window in day_windows]
        total_weight = sum(weights, Decimal("0"))
        if total_weight <= 0:
            continue
        for window, weight in zip(day_windows, weights):
            if window.product_mapping.product_id is None or window.bucket.bucket_id is None:
                continue
            allocations.append(
                DailyIssueAllocation(
                    issue_key=window.evidence.issue_key,
                    team_member_id=window.evidence.team_member_id,
                    product_id=window.product_mapping.product_id,
                    bucket_id=window.bucket.bucket_id,
                    allocation_date=day,
                    allocated_hours=estimated_day_hours * weight / total_weight,
                    day_capacity_hours=daily_capacity,
                    active_ticket_count=len(day_windows),
                )
            )
    return allocations


def persist_estimated_entries(
    db: Session,
    run: EstimationRun,
    allocations: list[DailyIssueAllocation],
    *,
    confidence_score: Decimal = Decimal("0.7500"),
    source_note: str = "Estimated from Jira issue activity",
) -> list[EstimatedEntry]:
    months = ensure_fiscal_months(db, run.fiscal_year)
    months_by_sequence = {month.sequence: month for month in months}
    grouped: dict[tuple[int, int, int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    for allocation in allocations:
        sequence = fiscal_sequence_for_date(allocation.allocation_date)
        month = months_by_sequence.get(sequence)
        if month is None:
            continue
        key = (allocation.product_id, allocation.team_member_id, allocation.bucket_id, month.id)
        grouped[key] += allocation.allocated_hours

    entries = []
    for (product_id, team_member_id, bucket_id, fiscal_month_id), hours in grouped.items():
        entry = EstimatedEntry(
            estimation_run_id=run.id,
            product_id=product_id,
            team_member_id=team_member_id,
            bucket_id=bucket_id,
            fiscal_month_id=fiscal_month_id,
            hours=hours.quantize(Decimal("0.01")),
            method_version=run.method_version,
            confidence_score=confidence_score,
            source_note=source_note,
        )
        db.add(entry)
        entries.append(entry)
    run.estimated_entry_count = len(entries)
    db.flush()
    return entries


def persist_estimated_issue_allocations(
    db: Session,
    run: EstimationRun,
    windows: list[IssueEstimationWindow],
    allocations: list[DailyIssueAllocation],
) -> list[EstimatedIssueAllocation]:
    months = ensure_fiscal_months(db, run.fiscal_year)
    months_by_sequence = {month.sequence: month for month in months}
    windows_by_issue = {window.evidence.issue_key: window for window in windows}
    grouped: dict[tuple[str, int, int, int, int], Decimal] = defaultdict(lambda: Decimal("0"))

    for allocation in allocations:
        month = months_by_sequence.get(fiscal_sequence_for_date(allocation.allocation_date))
        if month is None:
            continue
        key = (
            allocation.issue_key,
            allocation.team_member_id,
            allocation.product_id,
            allocation.bucket_id,
            month.id,
        )
        grouped[key] += allocation.allocated_hours

    audit_rows: list[EstimatedIssueAllocation] = []
    included_issue_keys = set()
    for (issue_key, team_member_id, product_id, bucket_id, fiscal_month_id), hours in grouped.items():
        window = windows_by_issue[issue_key]
        included_issue_keys.add(issue_key)
        row = _issue_allocation_row(
            run,
            window,
            product_id=product_id,
            bucket_id=bucket_id,
            fiscal_month_id=fiscal_month_id,
            allocated_hours=hours.quantize(Decimal("0.01")),
            included=True,
            inclusion_reason=window.inclusion_reason,
            exclusion_reason=None,
            team_member_id=team_member_id,
        )
        db.add(row)
        audit_rows.append(row)

    for window in windows:
        if not window.included:
            row = _issue_allocation_row(
                run,
                window,
                product_id=window.product_mapping.product_id,
                bucket_id=window.bucket.bucket_id,
                fiscal_month_id=None,
                allocated_hours=Decimal("0.00"),
                included=False,
                inclusion_reason=None,
                exclusion_reason=window.exclusion_reason,
            )
            db.add(row)
            audit_rows.append(row)
        elif window.evidence.issue_key not in included_issue_keys:
            fiscal_month = _fiscal_month_for_date(months, window.active_start)
            row = _issue_allocation_row(
                run,
                window,
                product_id=window.product_mapping.product_id,
                bucket_id=window.bucket.bucket_id,
                fiscal_month_id=fiscal_month.id if fiscal_month else None,
                allocated_hours=Decimal("0.00"),
                included=True,
                inclusion_reason="Included by estimation policy but no business-day allocation was produced",
                exclusion_reason=None,
            )
            db.add(row)
            audit_rows.append(row)

    db.flush()
    return audit_rows


def preview_mock_estimation(
    db: Session,
    fiscal_year: int,
    *,
    profile_id: int | None = None,
) -> EstimationRunSummary:
    profile = _estimation_profile_for_run(db, profile_id)
    issues = mock_estimation_issues(db, fiscal_year)
    windows = build_issue_estimation_windows(db, profile, fiscal_year, issues)
    allocations = allocate_daily_hours(windows, monthly_capacity_hours=profile.monthly_capacity_hours)
    return _estimation_summary(profile, fiscal_year, issues, windows, allocations, status="preview")


def run_mock_estimation(
    db: Session,
    fiscal_year: int,
    *,
    profile_id: int | None = None,
) -> EstimationRunSummary:
    profile = _estimation_profile_for_run(db, profile_id)
    issues = mock_estimation_issues(db, fiscal_year)
    updated_values = [issue.updated_at_from_jira for issue in issues if issue.updated_at_from_jira is not None]
    run = create_estimation_run(
        db,
        profile,
        fiscal_year,
        source_jira_updated_from=min(updated_values) if updated_values else None,
        source_jira_updated_to=max(updated_values) if updated_values else None,
    )
    windows = build_issue_estimation_windows(db, profile, fiscal_year, issues)
    allocations = allocate_daily_hours(windows, monthly_capacity_hours=profile.monthly_capacity_hours)
    persist_estimated_issue_allocations(db, run, windows, allocations)
    entries = persist_estimated_entries(db, run, allocations)
    summary = _estimation_summary(profile, fiscal_year, issues, windows, allocations, run_id=run.id, status="completed")
    complete_estimation_run(
        db,
        run,
        imported_issue_count=summary.imported_issue_count,
        estimated_entry_count=len(entries),
        warning_count=summary.warning_count,
        status="completed",
    )
    return summary


def mock_estimation_issues(db: Session, fiscal_year: int) -> list[EstimationIssueEvidence]:
    members = db.scalars(select(TeamMember).order_by(TeamMember.name)).all()
    if not members:
        return []

    def member_id(preferred_name: str, fallback_index: int) -> int:
        for member in members:
            if member.name == preferred_name:
                return member.id
        return members[min(fallback_index, len(members) - 1)].id

    avery_id = member_id("Avery Johnson", 0)
    morgan_id = member_id("Morgan Lee", 1)
    sam_id = member_id("Sam Patel", 2)
    riley_id = member_id("Riley Chen", 3)
    jordan_id = member_id("Jordan Smith", 4)

    return [
        EstimationIssueEvidence(
            team_member_id=avery_id,
            issue_id="900101",
            issue_key="CCTE-101",
            issue_summary="Case management intake modernization",
            jira_project_key="CCTE",
            jira_project_name="CCTE",
            issue_status="In Progress",
            status_category="In Progress",
            issue_type="Story",
            story_points=Decimal("5"),
            issue_logged_hours=Decimal("2"),
            created_at_from_jira=datetime(fiscal_year, 5, 1, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 12, 15),
            source_work_type="Net New",
        ),
        EstimationIssueEvidence(
            team_member_id=morgan_id,
            issue_id="900102",
            issue_key="TISA-204",
            issue_summary="Award eligibility review improvements",
            jira_project_key="TISA",
            jira_project_name="TISA",
            issue_status="Done",
            status_category="Done",
            issue_type="Task",
            story_points=Decimal("3"),
            issue_logged_hours=Decimal("0"),
            created_at_from_jira=datetime(fiscal_year, 4, 15, 8),
            updated_at_from_jira=datetime(fiscal_year, 4, 23, 16),
            resolved_at_from_jira=datetime(fiscal_year, 4, 23, 16),
            source_work_type="Enhancement",
        ),
        EstimationIssueEvidence(
            team_member_id=riley_id,
            issue_id="900103",
            issue_key="RC-77",
            issue_summary="Reporting center extract tuning",
            jira_project_key="RC",
            jira_project_name="RC",
            issue_status="In Progress",
            status_category="In Progress",
            issue_type="Bug",
            story_points=Decimal("2"),
            issue_logged_hours=Decimal("0"),
            created_at_from_jira=datetime(fiscal_year, 3, 3, 9),
            updated_at_from_jira=datetime(fiscal_year, 3, 13, 13),
            source_work_type="Bug Fix",
        ),
        EstimationIssueEvidence(
            team_member_id=sam_id,
            issue_id="900104",
            issue_key="GOV-42",
            issue_summary="Governance access review support",
            jira_project_key="GOV",
            jira_project_name="Governance",
            issue_status="Done",
            status_category="Done",
            issue_type="Routine Task",
            story_points=Decimal("0"),
            issue_logged_hours=Decimal("1"),
            created_at_from_jira=datetime(fiscal_year, 2, 3, 9),
            updated_at_from_jira=datetime(fiscal_year, 2, 11, 17),
            resolved_at_from_jira=datetime(fiscal_year, 2, 11, 17),
            source_work_type="Support",
        ),
        EstimationIssueEvidence(
            team_member_id=jordan_id,
            issue_id="900105",
            issue_key="RPA-18",
            issue_summary="Automation exception handling",
            jira_project_key="RPA",
            jira_project_name="RPA",
            issue_status="In Progress",
            status_category="In Progress",
            issue_type="Story",
            story_points=Decimal("3"),
            issue_logged_hours=Decimal("0"),
            created_at_from_jira=datetime(fiscal_year, 5, 6, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 14, 10),
            source_work_type="Enhance Existing",
        ),
        EstimationIssueEvidence(
            team_member_id=avery_id,
            issue_id="900106",
            issue_key="CCTE-118",
            issue_summary="Operational clean-up with missing work type",
            jira_project_key="CCTE",
            jira_project_name="CCTE",
            issue_status="In Progress",
            status_category="In Progress",
            issue_type="Task",
            story_points=Decimal("1"),
            issue_logged_hours=Decimal("0"),
            created_at_from_jira=datetime(fiscal_year, 5, 8, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 14, 12),
            source_work_type="",
        ),
        EstimationIssueEvidence(
            team_member_id=sam_id,
            issue_id="900107",
            issue_key="ROADMAP-7",
            issue_summary="Portfolio roadmap placeholder",
            jira_project_key="ROADMAP",
            jira_project_name="Roadmap",
            issue_status="In Progress",
            status_category="In Progress",
            issue_type="Task",
            created_at_from_jira=datetime(fiscal_year, 5, 2, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 3, 10),
            source_work_type="Net New",
        ),
        EstimationIssueEvidence(
            team_member_id=morgan_id,
            issue_id="900108",
            issue_key="ZZZ-1",
            issue_summary="Unknown project reference for mapping review",
            jira_project_key="ZZZ",
            jira_project_name="Mystery Project",
            issue_status="In Progress",
            status_category="In Progress",
            issue_type="Task",
            created_at_from_jira=datetime(fiscal_year, 5, 5, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 9, 10),
            source_work_type="Enhance",
        ),
        EstimationIssueEvidence(
            team_member_id=riley_id,
            issue_id="900109",
            issue_key="CCTE-119",
            issue_summary="Paused integration dependency",
            jira_project_key="CCTE",
            jira_project_name="CCTE",
            issue_status="On Hold",
            status_category="In Progress",
            issue_type="Task",
            created_at_from_jira=datetime(fiscal_year, 5, 1, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 10, 10),
            source_work_type="Maintenance",
        ),
        EstimationIssueEvidence(
            team_member_id=jordan_id,
            issue_id="900110",
            issue_key="TISA-205",
            issue_summary="Ready backlog item without activity",
            jira_project_key="TISA",
            jira_project_name="TISA",
            issue_status="Ready for Development",
            status_category="To Do",
            issue_type="Story",
            created_at_from_jira=datetime(fiscal_year, 5, 1, 9),
            updated_at_from_jira=datetime(fiscal_year, 5, 1, 9),
            source_work_type="New Feature",
        ),
    ]


def reported_effective_value(
    *,
    forecast_hours: Decimal | float | int | None,
    actual_hours: Decimal | float | int | None,
    estimated_hours: Decimal | float | int | None,
    month_closed: bool,
    future_or_planning_month: bool,
    actual_completeness_threshold: Decimal | float | int = DEFAULT_ACTUAL_COMPLETENESS_THRESHOLD,
) -> ReportedValueDecision:
    forecast = Decimal(str(forecast_hours or 0))
    actual = Decimal(str(actual_hours or 0))
    estimated = Decimal(str(estimated_hours or 0))
    threshold = Decimal(str(actual_completeness_threshold))

    if month_closed and estimated > 0 and actual >= estimated * threshold:
        return ReportedValueDecision(actual, "actual", "Actual complete")
    if month_closed and actual > 0 and estimated <= 0:
        return ReportedValueDecision(actual, "actual", "Actual logged")
    if estimated > 0:
        return ReportedValueDecision(estimated, "estimated", "Used estimate because actual logging incomplete")
    if future_or_planning_month and forecast > 0:
        return ReportedValueDecision(forecast, "forecast", "Used forecast for future/planning period")
    return ReportedValueDecision(Decimal("0"), "none", "No reportable hours by rule")


def reported_value_rows(
    db: Session,
    fiscal_year: int,
    *,
    product_id: int | None = None,
    team_member_id: int | None = None,
    as_of: date | None = None,
) -> list[dict[str, object]]:
    as_of = as_of or date.today()
    months = ensure_fiscal_months(db, fiscal_year)
    months_by_id = {month.id: month for month in months}
    forecast_by_key = _aggregate_entries(db, ForecastEntry, fiscal_year, product_id, team_member_id)
    actual_by_key = _aggregate_entries(db, ActualEntry, fiscal_year, product_id, team_member_id)
    latest_run = _latest_estimation_run(db, fiscal_year)
    estimated_by_key = (
        _aggregate_entries(db, EstimatedEntry, fiscal_year, product_id, team_member_id, estimation_run_id=latest_run.id)
        if latest_run
        else {}
    )
    profile = latest_run.profile if latest_run else db.scalar(select(EstimationProfile).where(EstimationProfile.is_active.is_(True)))
    threshold = profile.actual_completeness_threshold if profile else DEFAULT_ACTUAL_COMPLETENESS_THRESHOLD
    keys = set(forecast_by_key) | set(actual_by_key) | set(estimated_by_key)
    products_by_id = {row.id: row for row in db.scalars(select(Product).where(Product.id.in_({key[0] for key in keys}))).all()} if keys else {}
    members_by_id = {row.id: row for row in db.scalars(select(TeamMember).where(TeamMember.id.in_({key[1] for key in keys}))).all()} if keys else {}
    buckets_by_id = {row.id: row for row in db.scalars(select(Bucket).where(Bucket.id.in_({key[2] for key in keys}))).all()} if keys else {}

    rows = []
    for key in sorted(keys, key=lambda value: (products_by_id[value[0]].name, members_by_id[value[1]].name, buckets_by_id[value[2]].name, months_by_id[value[3]].sequence)):
        row_product_id, row_member_id, row_bucket_id, month_id = key
        month = months_by_id[month_id]
        forecast = forecast_by_key.get(key, Decimal("0"))
        actual = actual_by_key.get(key, Decimal("0"))
        estimated = estimated_by_key.get(key, Decimal("0"))
        decision = reported_effective_value(
            forecast_hours=forecast,
            actual_hours=actual,
            estimated_hours=estimated,
            month_closed=month.ends_on < as_of,
            future_or_planning_month=month.ends_on >= as_of,
            actual_completeness_threshold=threshold,
        )
        rows.append(
            {
                "product_id": row_product_id,
                "product": products_by_id[row_product_id].name,
                "product_slug": product_url_slug(products_by_id[row_product_id]),
                "program_area": products_by_id[row_product_id].office,
                "team_member_id": row_member_id,
                "team_member": members_by_id[row_member_id].name,
                "team_member_slug": team_member_url_slug(members_by_id[row_member_id]),
                "bucket_id": row_bucket_id,
                "bucket": buckets_by_id[row_bucket_id].name,
                "bucket_code": buckets_by_id[row_bucket_id].code,
                "fiscal_month_id": month_id,
                "month_label": month.label,
                "month_sequence": month.sequence,
                "calendar_year": month.calendar_year,
                "calendar_month": month.calendar_month,
                "forecast_hours": round(float(forecast), 2),
                "actual_hours": round(float(actual), 2),
                "estimated_hours": round(float(estimated), 2),
                "reported_hours": round(float(decision.hours), 2),
                "reported_source": decision.source,
                "reported_reason": decision.reason,
                "estimation_run_id": latest_run.id if latest_run else None,
            }
        )
    return rows


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def normalize_lookup_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", clean(value).casefold())


def _aggregate_entries(
    db: Session,
    model,
    fiscal_year: int,
    product_id: int | None,
    team_member_id: int | None,
    *,
    estimation_run_id: int | None = None,
) -> dict[tuple[int, int, int, int], Decimal]:
    statement = select(model).join(model.fiscal_month).where(FiscalMonth.fiscal_year == fiscal_year)
    if product_id is not None:
        statement = statement.where(model.product_id == product_id)
    if team_member_id is not None:
        statement = statement.where(model.team_member_id == team_member_id)
    if estimation_run_id is not None:
        statement = statement.where(model.estimation_run_id == estimation_run_id)

    by_key: dict[tuple[int, int, int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    for entry in db.scalars(statement).all():
        key = (entry.product_id, entry.team_member_id, entry.bucket_id, entry.fiscal_month_id)
        by_key[key] += entry.hours
    return by_key


def _latest_estimation_run(db: Session, fiscal_year: int) -> EstimationRun | None:
    return db.scalar(
        select(EstimationRun)
        .where(
            EstimationRun.fiscal_year == fiscal_year,
            EstimationRun.status == "completed",
        )
        .order_by(EstimationRun.completed_at.desc(), EstimationRun.id.desc())
        .limit(1)
    )


def _estimation_profile_for_run(db: Session, profile_id: int | None) -> EstimationProfile:
    if profile_id is not None:
        profile = db.get(EstimationProfile, profile_id)
        if profile is not None:
            return profile
        raise ValueError("Estimation profile not found")
    active_profile = db.scalar(select(EstimationProfile).where(EstimationProfile.is_active.is_(True)))
    return active_profile or ensure_default_estimation_profile(db)


def _estimation_summary(
    profile: EstimationProfile,
    fiscal_year: int,
    issues: list[EstimationIssueEvidence],
    windows: list[IssueEstimationWindow],
    allocations: list[DailyIssueAllocation],
    *,
    run_id: int | None = None,
    status: str = "preview",
) -> EstimationRunSummary:
    warnings = _estimation_warnings(windows, issues)
    included_issue_count = len([window for window in windows if window.included])
    excluded_issue_count = len(windows) - included_issue_count
    unmapped_issue_count = len([window for window in windows if window.product_mapping.status == "unmapped"])
    estimated_hours = sum((allocation.allocated_hours for allocation in allocations), Decimal("0")).quantize(Decimal("0.01"))
    return EstimationRunSummary(
        fiscal_year=fiscal_year,
        profile_id=profile.id,
        method_version=profile.method_version,
        imported_issue_count=len(issues),
        included_issue_count=included_issue_count,
        excluded_issue_count=excluded_issue_count,
        unmapped_issue_count=unmapped_issue_count,
        estimated_entry_count=_estimated_entry_count(allocations),
        estimated_hours=estimated_hours,
        warning_count=len(warnings),
        warnings=warnings,
        run_id=run_id,
        status=status,
    )


def _estimated_entry_count(allocations: list[DailyIssueAllocation]) -> int:
    keys = {
        (
            allocation.product_id,
            allocation.team_member_id,
            allocation.bucket_id,
            fiscal_sequence_for_date(allocation.allocation_date),
        )
        for allocation in allocations
    }
    return len(keys)


def _estimation_warnings(windows: list[IssueEstimationWindow], issues: list[EstimationIssueEvidence]) -> list[str]:
    warnings: list[str] = []
    if not issues:
        warnings.append("No Jira issue evidence was available for estimation.")
    unmapped_keys = sorted({window.product_mapping.jira_project_key for window in windows if window.product_mapping.status == "unmapped"})
    excluded_project_keys = sorted({window.product_mapping.jira_project_key for window in windows if window.product_mapping.status == "excluded"})
    status_excluded = [window for window in windows if window.exclusion_reason and "status" in window.exclusion_reason.casefold()]
    defaulted_buckets = sorted({window.evidence.issue_key for window in windows if window.bucket.defaulted})
    if unmapped_keys:
        warnings.append(f"Unmapped Jira project keys require review: {', '.join(unmapped_keys)}.")
    if excluded_project_keys:
        warnings.append(f"Excluded Jira project keys were ignored by policy: {', '.join(excluded_project_keys)}.")
    if status_excluded:
        warnings.append(f"{len(status_excluded)} issue(s) were excluded by status or low-activity status policy.")
    if defaulted_buckets:
        warnings.append(f"{len(defaulted_buckets)} issue(s) defaulted to Maintenance because no recognized work type was found.")
    return warnings


def _issue_allocation_row(
    run: EstimationRun,
    window: IssueEstimationWindow,
    *,
    product_id: int | None,
    bucket_id: int | None,
    fiscal_month_id: int | None,
    allocated_hours: Decimal,
    included: bool,
    inclusion_reason: str | None,
    exclusion_reason: str | None,
    team_member_id: int | None = None,
) -> EstimatedIssueAllocation:
    issue = window.evidence
    return EstimatedIssueAllocation(
        estimation_run_id=run.id,
        team_member_id=team_member_id or issue.team_member_id,
        issue_id=issue.issue_id,
        issue_key=issue.issue_key,
        issue_summary=issue.issue_summary,
        jira_project_key=window.product_mapping.jira_project_key,
        product_id=product_id,
        bucket_id=bucket_id,
        fiscal_month_id=fiscal_month_id,
        allocated_hours=allocated_hours,
        issue_status=issue.issue_status,
        status_category=issue.status_category,
        issue_type=issue.issue_type,
        story_points=issue.story_points,
        issue_logged_hours=issue.issue_logged_hours,
        created_at_from_jira=issue.created_at_from_jira,
        updated_at_from_jira=issue.updated_at_from_jira,
        resolved_at_from_jira=issue.resolved_at_from_jira,
        active_window_start=window.active_start,
        active_window_end=window.active_end,
        included=included,
        inclusion_reason=inclusion_reason,
        exclusion_reason=exclusion_reason,
    )


def _fiscal_month_for_date(months: list[FiscalMonth], value: date | None) -> FiscalMonth | None:
    if value is None:
        return None
    for month in months:
        if month.starts_on <= value <= month.ends_on:
            return month
    return None


def iter_business_days(start: date, end: date):
    current = start
    while current <= end:
        if current.weekday() < 5:
            yield current
        current += timedelta(days=1)


def business_days_in_month(value: date) -> int:
    return sum(1 for _day in iter_business_days(value, date(value.year, value.month, calendar.monthrange(value.year, value.month)[1])))


def _excluded_window(
    issue: EstimationIssueEvidence,
    mapping: ProductMappingDecision,
    bucket: BucketDecision,
    reason: str,
    effort: Decimal,
) -> IssueEstimationWindow:
    return IssueEstimationWindow(
        evidence=issue,
        product_mapping=mapping,
        bucket=bucket,
        included=False,
        inclusion_reason=None,
        exclusion_reason=reason,
        active_start=None,
        active_end=None,
        effort_weight=effort,
        coverage_weight=Decimal("0"),
    )


def _ensure_unmapped_product_reference(db: Session, jira_project_key: str, jira_project_name: str) -> JiraProductMapping:
    mapping = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == jira_project_key))
    if mapping is not None:
        return mapping
    mapping = JiraProductMapping(
        jira_project_key=jira_project_key,
        jira_project_name=clean(jira_project_name) or jira_project_key,
        product_id=None,
    )
    db.add(mapping)
    db.flush()
    return mapping


def _project_pause_dates(profile: EstimationProfile) -> dict[str, date]:
    raw = _loads_dict(profile.project_pause_dates)
    dates: dict[str, date] = {}
    for key, value in raw.items():
        if not value:
            continue
        dates[clean(key).upper()] = date.fromisoformat(str(value))
    return dates


def _loads_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return [clean(item) for item in value.split(",") if clean(item)]
    if isinstance(parsed, list):
        return [clean(item) for item in parsed if clean(item)]
    return []


def _loads_dict(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
