from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.errors import bad_request
from app.db.session import get_db
from app.models import FiscalMonth, ForecastEntry
from app.schemas import ForecastBatchUpsert, ForecastResponse, ForecastUpsert
from app.services.costs import round_hours
from app.services.forecasting import upsert_forecast_entry

router = APIRouter(prefix="/forecasts", tags=["forecasts"])


@router.get("")
def list_forecasts(
    product_id: int | None = None,
    team_member_id: int | None = None,
    fiscal_year: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    statement = select(ForecastEntry).options(
        joinedload(ForecastEntry.product),
        joinedload(ForecastEntry.team_member),
        joinedload(ForecastEntry.bucket),
        joinedload(ForecastEntry.fiscal_month),
    )
    if fiscal_year is not None:
        statement = statement.join(ForecastEntry.fiscal_month).where(FiscalMonth.fiscal_year == fiscal_year)
    if product_id is not None:
        statement = statement.where(ForecastEntry.product_id == product_id)
    if team_member_id is not None:
        statement = statement.where(ForecastEntry.team_member_id == team_member_id)

    entries = db.scalars(statement).all()
    return [
        {
            "id": entry.id,
            "product_id": entry.product_id,
            "product": entry.product.name,
            "team_member_id": entry.team_member_id,
            "team_member": entry.team_member.name,
            "bucket_id": entry.bucket_id,
            "bucket": entry.bucket.name,
            "fiscal_month_id": entry.fiscal_month_id,
            "fiscal_year": entry.fiscal_month.fiscal_year,
            "month_sequence": entry.fiscal_month.sequence,
            "month_label": entry.fiscal_month.label,
            "hours": round_hours(entry.hours),
        }
        for entry in entries
    ]


@router.put("", response_model=ForecastResponse)
def upsert_forecast(payload: ForecastUpsert, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        entry = upsert_forecast_entry(db, **payload.model_dump())
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "product_id": entry.product_id,
        "team_member_id": entry.team_member_id,
        "bucket_id": entry.bucket_id,
        "fiscal_month_id": entry.fiscal_month_id,
        "hours": round_hours(entry.hours),
    }


@router.put("/batch", response_model=list[ForecastResponse])
def upsert_forecast_batch(payload: ForecastBatchUpsert, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    entries = []
    try:
        for item in payload.entries:
            entries.append(upsert_forecast_entry(db, **item.model_dump()))
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return [
        {
            "id": entry.id,
            "product_id": entry.product_id,
            "team_member_id": entry.team_member_id,
            "bucket_id": entry.bucket_id,
            "fiscal_month_id": entry.fiscal_month_id,
            "hours": round_hours(entry.hours),
        }
        for entry in entries
    ]
