from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import not_found
from app.db.session import get_db
from app.models import EstimatedIssueAllocation, EstimationProfile, EstimationRun
from app.schemas import (
    EstimatedIssueAllocationResponse,
    EstimationProfileResponse,
    EstimationProfileUpdate,
    EstimationPreviewResponse,
    EstimationRunRequest,
    EstimationRunResponse,
    ReportedValueRowResponse,
    TeamMemberStoryPointMetricResponse,
)
from app.services.estimation_policy import ensure_default_estimation_profile, preview_mock_estimation, reported_value_rows, run_mock_estimation

router = APIRouter(prefix="/estimations", tags=["estimations"])


@router.get("/profiles", response_model=list[EstimationProfileResponse])
def list_estimation_profiles(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    ensure_default_estimation_profile(db)
    db.commit()
    profiles = db.scalars(select(EstimationProfile).order_by(EstimationProfile.name)).all()
    return [_serialize_profile(profile) for profile in profiles]


@router.put("/profiles/{profile_id}", response_model=EstimationProfileResponse)
def update_estimation_profile(
    profile_id: int,
    payload: EstimationProfileUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    profile = db.get(EstimationProfile, profile_id)
    if profile is None:
        raise not_found("Estimation profile")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(profile, key, value)
    db.commit()
    db.refresh(profile)
    return _serialize_profile(profile)


@router.get("/runs", response_model=list[EstimationRunResponse])
def list_estimation_runs(
    fiscal_year: int | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    statement = select(EstimationRun).order_by(EstimationRun.started_at.desc())
    if fiscal_year is not None:
        statement = statement.where(EstimationRun.fiscal_year == fiscal_year)
    statement = statement.limit(limit)
    return [_serialize_run(run) for run in db.scalars(statement).all()]


@router.post("/preview", response_model=EstimationPreviewResponse)
def preview_estimation(
    payload: EstimationRunRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_profile(db, payload.profile_id)
    summary = preview_mock_estimation(db, payload.fiscal_year, profile_id=payload.profile_id)
    db.commit()
    return _serialize_summary(summary)


@router.post("/run", response_model=EstimationPreviewResponse)
def run_estimation(
    payload: EstimationRunRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_profile(db, payload.profile_id)
    summary = run_mock_estimation(db, payload.fiscal_year, profile_id=payload.profile_id)
    db.commit()
    return _serialize_summary(summary)


@router.get("/runs/{run_id}/allocations", response_model=list[EstimatedIssueAllocationResponse])
def list_estimation_run_allocations(
    run_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    if db.get(EstimationRun, run_id) is None:
        raise not_found("Estimation run")
    statement = (
        select(EstimatedIssueAllocation)
        .where(EstimatedIssueAllocation.estimation_run_id == run_id)
        .order_by(EstimatedIssueAllocation.included, EstimatedIssueAllocation.issue_key, EstimatedIssueAllocation.id)
        .limit(limit)
    )
    return [_serialize_allocation(row) for row in db.scalars(statement).all()]


@router.get("/story-point-metrics", response_model=list[TeamMemberStoryPointMetricResponse])
def list_team_member_story_point_metrics(
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    latest_run = db.scalar(
        select(EstimationRun)
        .where(EstimationRun.fiscal_year == fiscal_year, EstimationRun.status == "completed")
        .order_by(EstimationRun.started_at.desc())
        .limit(1)
    )
    if latest_run is None:
        return []

    allocations = db.scalars(
        select(EstimatedIssueAllocation).where(
            EstimatedIssueAllocation.estimation_run_id == latest_run.id,
            EstimatedIssueAllocation.included.is_(True),
        )
    ).all()
    return _serialize_team_member_story_point_metrics(latest_run.id, allocations)


@router.get("/reported-values", response_model=list[ReportedValueRowResponse])
def get_reported_values(
    fiscal_year: int = 2027,
    product_id: int | None = None,
    team_member_id: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return reported_value_rows(db, fiscal_year, product_id=product_id, team_member_id=team_member_id)


def _serialize_profile(profile: EstimationProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "is_active": profile.is_active,
        "method_version": profile.method_version,
        "monthly_capacity_hours": float(profile.monthly_capacity_hours),
        "actual_completeness_threshold": float(profile.actual_completeness_threshold),
        "stale_ticket_window_days": profile.stale_ticket_window_days,
        "forecast_future_months": profile.forecast_future_months,
        "future_month_average_window": profile.future_month_average_window,
        "excluded_statuses": profile.excluded_statuses,
        "low_activity_statuses": profile.low_activity_statuses,
        "excluded_jira_project_keys": profile.excluded_jira_project_keys,
        "project_pause_dates": profile.project_pause_dates,
        "work_type_field_priority": profile.work_type_field_priority,
        "story_point_weighting_enabled": profile.story_point_weighting_enabled,
        "notes": profile.notes,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


def _require_profile(db: Session, profile_id: int | None) -> None:
    if profile_id is not None and db.get(EstimationProfile, profile_id) is None:
        raise not_found("Estimation profile")


def _serialize_run(run: EstimationRun) -> dict[str, object]:
    return {
        "id": run.id,
        "profile_id": run.profile_id,
        "method_version": run.method_version,
        "fiscal_year": run.fiscal_year,
        "source_jira_updated_from": run.source_jira_updated_from,
        "source_jira_updated_to": run.source_jira_updated_to,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "status": run.status,
        "imported_issue_count": run.imported_issue_count,
        "estimated_entry_count": run.estimated_entry_count,
        "warning_count": run.warning_count,
        "error_summary": run.error_summary,
        "created_at": run.created_at,
        "updated_at": run.updated_at,
    }


def _serialize_summary(summary) -> dict[str, object]:
    return {
        "fiscal_year": summary.fiscal_year,
        "profile_id": summary.profile_id,
        "method_version": summary.method_version,
        "imported_issue_count": summary.imported_issue_count,
        "included_issue_count": summary.included_issue_count,
        "excluded_issue_count": summary.excluded_issue_count,
        "unmapped_issue_count": summary.unmapped_issue_count,
        "estimated_entry_count": summary.estimated_entry_count,
        "estimated_hours": float(summary.estimated_hours),
        "warning_count": summary.warning_count,
        "warnings": summary.warnings,
        "run_id": summary.run_id,
        "status": summary.status,
    }


def _serialize_team_member_story_point_metrics(estimation_run_id: int, allocations: list[EstimatedIssueAllocation]) -> list[dict[str, object]]:
    unique_issue_rows: dict[tuple[int, str], EstimatedIssueAllocation] = {}
    for allocation in allocations:
        unique_issue_rows.setdefault((allocation.team_member_id, allocation.issue_key), allocation)

    totals: dict[int, dict[str, Decimal | int]] = {}
    for allocation in unique_issue_rows.values():
        member_totals = totals.setdefault(
            allocation.team_member_id,
            {"story_points": Decimal("0"), "issue_logged_hours": Decimal("0"), "issue_count": 0},
        )
        member_totals["story_points"] += allocation.story_points or Decimal("0")
        member_totals["issue_logged_hours"] += allocation.issue_logged_hours
        member_totals["issue_count"] += 1

    rows: list[dict[str, object]] = []
    for team_member_id, member_totals in totals.items():
        story_points = Decimal(member_totals["story_points"])
        logged_hours = Decimal(member_totals["issue_logged_hours"])
        rows.append(
            {
                "estimation_run_id": estimation_run_id,
                "team_member_id": team_member_id,
                "story_points": float(story_points),
                "issue_logged_hours": float(logged_hours),
                "story_points_per_logged_hour": float((story_points / logged_hours).quantize(Decimal("0.01"))) if logged_hours > 0 else None,
                "issue_count": member_totals["issue_count"],
            }
        )

    return sorted(rows, key=lambda row: (-float(row["story_points"]), row["team_member_id"]))


def _serialize_allocation(allocation: EstimatedIssueAllocation) -> dict[str, object]:
    return {
        "id": allocation.id,
        "estimation_run_id": allocation.estimation_run_id,
        "team_member_id": allocation.team_member_id,
        "team_member": allocation.team_member.name,
        "issue_id": allocation.issue_id,
        "issue_key": allocation.issue_key,
        "issue_summary": allocation.issue_summary,
        "jira_project_key": allocation.jira_project_key,
        "product_id": allocation.product_id,
        "product": allocation.product.name if allocation.product else None,
        "bucket_id": allocation.bucket_id,
        "bucket": allocation.bucket.name if allocation.bucket else None,
        "fiscal_month_id": allocation.fiscal_month_id,
        "month_label": allocation.fiscal_month.label if allocation.fiscal_month else None,
        "allocated_hours": float(allocation.allocated_hours),
        "issue_status": allocation.issue_status,
        "status_category": allocation.status_category,
        "issue_type": allocation.issue_type,
        "story_points": float(allocation.story_points) if allocation.story_points is not None else None,
        "issue_logged_hours": float(allocation.issue_logged_hours),
        "created_at_from_jira": allocation.created_at_from_jira,
        "updated_at_from_jira": allocation.updated_at_from_jira,
        "resolved_at_from_jira": allocation.resolved_at_from_jira,
        "active_window_start": allocation.active_window_start,
        "active_window_end": allocation.active_window_end,
        "included": allocation.included,
        "inclusion_reason": allocation.inclusion_reason,
        "exclusion_reason": allocation.exclusion_reason,
    }
