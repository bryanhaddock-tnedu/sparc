from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Bucket, FiscalMonth, ForecastEntry
from app.services.fiscal_year import get_fiscal_month


def resolve_fiscal_month(
    db: Session,
    *,
    fiscal_month_id: int | None = None,
    fiscal_year: int | None = None,
    month_sequence: int | None = None,
) -> FiscalMonth:
    if fiscal_month_id is not None:
        month = db.get(FiscalMonth, fiscal_month_id)
        if month is None:
            raise ValueError("Fiscal month not found")
        return month
    if fiscal_year is None or month_sequence is None:
        raise ValueError("Either fiscal_month_id or fiscal_year plus month_sequence is required")
    return get_fiscal_month(db, fiscal_year, month_sequence)


def resolve_bucket(db: Session, *, bucket_id: int | None = None, bucket_code: str | None = None) -> Bucket:
    if bucket_id is not None:
        bucket = db.get(Bucket, bucket_id)
    elif bucket_code is not None:
        bucket = db.scalar(select(Bucket).where(Bucket.code == bucket_code))
    else:
        raise ValueError("Either bucket_id or bucket_code is required")
    if bucket is None:
        raise ValueError("Bucket not found")
    return bucket


def upsert_forecast_entry(
    db: Session,
    *,
    product_id: int,
    team_member_id: int,
    hours: Decimal | float | int,
    bucket_id: int | None = None,
    bucket_code: str | None = None,
    fiscal_month_id: int | None = None,
    fiscal_year: int | None = None,
    month_sequence: int | None = None,
) -> ForecastEntry:
    month = resolve_fiscal_month(
        db,
        fiscal_month_id=fiscal_month_id,
        fiscal_year=fiscal_year,
        month_sequence=month_sequence,
    )
    bucket = resolve_bucket(db, bucket_id=bucket_id, bucket_code=bucket_code)
    entry = db.scalar(
        select(ForecastEntry).where(
            ForecastEntry.product_id == product_id,
            ForecastEntry.team_member_id == team_member_id,
            ForecastEntry.bucket_id == bucket.id,
            ForecastEntry.fiscal_month_id == month.id,
        )
    )
    if entry is None:
        entry = ForecastEntry(
            product_id=product_id,
            team_member_id=team_member_id,
            bucket_id=bucket.id,
            fiscal_month_id=month.id,
            hours=Decimal(str(hours)),
        )
        db.add(entry)
    else:
        entry.hours = Decimal(str(hours))
    db.flush()
    return entry
