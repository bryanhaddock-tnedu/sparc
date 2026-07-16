from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Bucket, FiscalMonth, ForecastEntry, ForecastRecommendationDecision, Product, TeamMember
from app.models.entities import utcnow
from app.services.costs import round_hours
from app.services.forecasting import upsert_forecast_entry
from app.services.fiscal_year import get_fiscal_month
from app.services.roadmap import roadmap_actual_rows
from app.services.slugs import product_url_slug

ACTION_APPLIED = "applied"
ACTION_REJECTED = "rejected"
RECOMMENDATION_ADD_FORECAST = "add_forecast"
RECOMMENDATION_INCREASE_FORECAST = "increase_forecast"
RECOMMENDATION_MONITOR = "monitor"
RECOMMENDATION_NONE = "none"


def create_forecast_recommendation_decision(
    db: Session,
    *,
    fiscal_year: int,
    product_id: int,
    bucket_id: int,
    action: str,
    expected_forecast_hours: Decimal | float | int,
    expected_roadmap_actual_hours: Decimal | float | int,
    target_team_member_id: int | None = None,
    target_month_sequence: int | None = None,
    note: str | None = None,
) -> dict[str, object]:
    if action not in {ACTION_APPLIED, ACTION_REJECTED}:
        raise ValueError("Forecast recommendation action must be applied or rejected")
    snapshot = _recommendation_snapshot(db, fiscal_year=fiscal_year, product_id=product_id, bucket_id=bucket_id)
    if not _reviewed_hours_match(snapshot["forecast_hours"], expected_forecast_hours) or not _reviewed_hours_match(
        snapshot["roadmap_actual_hours"], expected_roadmap_actual_hours
    ):
        raise ValueError("Forecast recommendation changed since this queue loaded. Refresh and review it before deciding")

    applied_entry: ForecastEntry | None = None
    if action == ACTION_APPLIED:
        if snapshot["recommendation"] not in {RECOMMENDATION_ADD_FORECAST, RECOMMENDATION_INCREASE_FORECAST}:
            raise ValueError("Only add/increase forecast recommendations can be applied")
        if snapshot["suggested_delta_hours"] <= 0:
            raise ValueError("Recommendation does not include additional forecast hours")
        if target_team_member_id is None:
            raise ValueError("Target team member is required to apply a forecast recommendation")
        if target_month_sequence is None:
            raise ValueError("Target fiscal month is required to apply a forecast recommendation")
        target_team_member = db.get(TeamMember, target_team_member_id)
        if target_team_member is None:
            raise ValueError("Target team member not found")
        if target_team_member.status != "active":
            raise ValueError("Target team member must be active")
        get_fiscal_month(db, fiscal_year, target_month_sequence)
        existing_hours = _existing_target_forecast_hours(
            db,
            product_id=product_id,
            bucket_id=bucket_id,
            team_member_id=target_team_member_id,
            fiscal_year=fiscal_year,
            month_sequence=target_month_sequence,
        )
        applied_entry = upsert_forecast_entry(
            db,
            product_id=product_id,
            team_member_id=target_team_member_id,
            bucket_id=bucket_id,
            fiscal_year=fiscal_year,
            month_sequence=target_month_sequence,
            hours=existing_hours + snapshot["suggested_delta_hours"],
        )

    decision = ForecastRecommendationDecision(
        fiscal_year=fiscal_year,
        product_id=product_id,
        bucket_id=bucket_id,
        recommendation=str(snapshot["recommendation"]),
        action=action,
        forecast_hours=snapshot["forecast_hours"],
        roadmap_actual_hours=snapshot["roadmap_actual_hours"],
        suggested_delta_hours=snapshot["suggested_delta_hours"],
        suggested_forecast_hours=snapshot["suggested_forecast_hours"],
        target_team_member_id=target_team_member_id if action == ACTION_APPLIED else None,
        target_month_sequence=target_month_sequence if action == ACTION_APPLIED else None,
        applied_forecast_entry_id=applied_entry.id if applied_entry else None,
        note=note.strip() if note and note.strip() else None,
        decided_at=utcnow(),
    )
    db.add(decision)
    db.flush()
    return serialize_forecast_recommendation_decision(decision)


def list_forecast_recommendation_decisions(db: Session, fiscal_year: int, limit: int = 50) -> list[dict[str, object]]:
    decisions = db.scalars(
        select(ForecastRecommendationDecision)
        .options(
            joinedload(ForecastRecommendationDecision.product),
            joinedload(ForecastRecommendationDecision.bucket),
            joinedload(ForecastRecommendationDecision.target_team_member),
        )
        .where(ForecastRecommendationDecision.fiscal_year == fiscal_year)
        .order_by(ForecastRecommendationDecision.decided_at.desc(), ForecastRecommendationDecision.id.desc())
        .limit(limit)
    ).all()
    return [serialize_forecast_recommendation_decision(decision) for decision in decisions]


def serialize_forecast_recommendation_decision(decision: ForecastRecommendationDecision) -> dict[str, object]:
    return {
        "id": decision.id,
        "fiscal_year": decision.fiscal_year,
        "product_id": decision.product_id,
        "product": decision.product.name if decision.product else None,
        "product_slug": product_url_slug(decision.product) if decision.product else None,
        "bucket_id": decision.bucket_id,
        "bucket": decision.bucket.name if decision.bucket else None,
        "recommendation": decision.recommendation,
        "action": decision.action,
        "forecast_hours": round_hours(decision.forecast_hours),
        "roadmap_actual_hours": round_hours(decision.roadmap_actual_hours),
        "suggested_delta_hours": round_hours(decision.suggested_delta_hours),
        "suggested_forecast_hours": round_hours(decision.suggested_forecast_hours),
        "target_team_member_id": decision.target_team_member_id,
        "target_team_member": decision.target_team_member.name if decision.target_team_member else None,
        "target_month_sequence": decision.target_month_sequence,
        "applied_forecast_entry_id": decision.applied_forecast_entry_id,
        "note": decision.note,
        "decided_at": decision.decided_at,
        "created_at": decision.created_at,
        "updated_at": decision.updated_at,
    }


def _recommendation_snapshot(db: Session, *, fiscal_year: int, product_id: int, bucket_id: int) -> dict[str, Decimal | str]:
    if db.get(Product, product_id) is None:
        raise ValueError("Product not found")
    if db.get(Bucket, bucket_id) is None:
        raise ValueError("Bucket not found")
    forecast_hours = _forecast_hours(db, fiscal_year=fiscal_year, product_id=product_id, bucket_id=bucket_id)
    roadmap_actual_hours = _roadmap_actual_hours(db, fiscal_year=fiscal_year, product_id=product_id, bucket_id=bucket_id)
    suggested_delta_hours = max(roadmap_actual_hours - forecast_hours, Decimal("0"))
    return {
        "forecast_hours": forecast_hours,
        "roadmap_actual_hours": roadmap_actual_hours,
        "suggested_delta_hours": suggested_delta_hours,
        "suggested_forecast_hours": forecast_hours + suggested_delta_hours,
        "recommendation": _recommendation_label(forecast_hours, roadmap_actual_hours),
    }


def _reviewed_hours_match(actual: Decimal | str, expected: Decimal | float | int) -> bool:
    return abs(Decimal(str(actual)) - Decimal(str(expected))) < Decimal("0.005")


def _recommendation_label(forecast_hours: Decimal, roadmap_actual_hours: Decimal) -> str:
    if forecast_hours <= 0 and roadmap_actual_hours > 0:
        return RECOMMENDATION_ADD_FORECAST
    if roadmap_actual_hours > forecast_hours:
        return RECOMMENDATION_INCREASE_FORECAST
    if forecast_hours > 0 and roadmap_actual_hours / forecast_hours >= Decimal("0.85"):
        return RECOMMENDATION_MONITOR
    return RECOMMENDATION_NONE


def _forecast_hours(db: Session, *, fiscal_year: int, product_id: int, bucket_id: int) -> Decimal:
    values = db.scalars(
        select(ForecastEntry.hours)
        .join(ForecastEntry.fiscal_month)
        .where(
            FiscalMonth.fiscal_year == fiscal_year,
            ForecastEntry.product_id == product_id,
            ForecastEntry.bucket_id == bucket_id,
        )
    ).all()
    return sum(values, Decimal("0"))


def _roadmap_actual_hours(db: Session, *, fiscal_year: int, product_id: int, bucket_id: int) -> Decimal:
    rows = roadmap_actual_rows(db, fiscal_year, product_id=product_id, bucket_id=bucket_id)
    return sum((Decimal(str(row["actual_hours"])) for row in rows if row["mapping_status"] == "mapped"), Decimal("0"))


def _existing_target_forecast_hours(
    db: Session,
    *,
    product_id: int,
    bucket_id: int,
    team_member_id: int,
    fiscal_year: int,
    month_sequence: int,
) -> Decimal:
    month = get_fiscal_month(db, fiscal_year, month_sequence)
    entry = db.scalar(
        select(ForecastEntry).where(
            ForecastEntry.product_id == product_id,
            ForecastEntry.bucket_id == bucket_id,
            ForecastEntry.team_member_id == team_member_id,
            ForecastEntry.fiscal_month_id == month.id,
        )
    )
    return entry.hours if entry else Decimal("0")
