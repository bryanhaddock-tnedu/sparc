from calendar import monthrange
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FiscalMonth

MONTH_LABELS = {
    1: "Jan",
    2: "Feb",
    3: "Mar",
    4: "Apr",
    5: "May",
    6: "Jun",
    7: "Jul",
    8: "Aug",
    9: "Sep",
    10: "Oct",
    11: "Nov",
    12: "Dec",
}


def fiscal_year_for_date(value: date) -> int:
    return value.year + 1 if value.month >= 7 else value.year


def current_fiscal_year(today: date | None = None) -> int:
    return fiscal_year_for_date(today or date.today())


def fiscal_sequence_for_date(value: date) -> int:
    return value.month - 6 if value.month >= 7 else value.month + 6


def fiscal_month_specs(fiscal_year: int) -> list[dict[str, object]]:
    specs: list[dict[str, object]] = []
    months = [(fiscal_year - 1, month) for month in range(7, 13)]
    months.extend((fiscal_year, month) for month in range(1, 7))

    for index, (calendar_year, calendar_month) in enumerate(months, start=1):
        last_day = monthrange(calendar_year, calendar_month)[1]
        specs.append(
            {
                "fiscal_year": fiscal_year,
                "sequence": index,
                "calendar_year": calendar_year,
                "calendar_month": calendar_month,
                "label": MONTH_LABELS[calendar_month],
                "starts_on": date(calendar_year, calendar_month, 1),
                "ends_on": date(calendar_year, calendar_month, last_day),
            }
        )
    return specs


def ensure_fiscal_months(db: Session, fiscal_year: int) -> list[FiscalMonth]:
    existing = db.scalars(
        select(FiscalMonth).where(FiscalMonth.fiscal_year == fiscal_year).order_by(FiscalMonth.sequence)
    ).all()
    if len(existing) == 12:
        return list(existing)

    by_sequence = {month.sequence: month for month in existing}
    for spec in fiscal_month_specs(fiscal_year):
        sequence = int(spec["sequence"])
        if sequence in by_sequence:
            continue
        db.add(FiscalMonth(**spec))
    db.flush()
    return list(
        db.scalars(select(FiscalMonth).where(FiscalMonth.fiscal_year == fiscal_year).order_by(FiscalMonth.sequence))
    )


def get_fiscal_month(db: Session, fiscal_year: int, sequence: int) -> FiscalMonth:
    ensure_fiscal_months(db, fiscal_year)
    month = db.scalar(
        select(FiscalMonth).where(FiscalMonth.fiscal_year == fiscal_year, FiscalMonth.sequence == sequence)
    )
    if month is None:
        raise ValueError(f"Fiscal month {sequence} for FY{fiscal_year} was not found")
    return month
