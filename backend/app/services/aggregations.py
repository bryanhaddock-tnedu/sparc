from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import ActualEntry, Bucket, FiscalMonth, ForecastEntry, Product, TeamMember
from app.services.costs import calculate_cost, round_hours
from app.services.fiscal_year import ensure_fiscal_months


def serialize_product(product: Product) -> dict[str, object]:
    return {
        "id": product.id,
        "name": product.name,
        "jira_space_key": product.jira_space_key,
        "description": product.description,
        "budget_amount": round(float(product.budget_amount or 0), 2),
        "is_active": product.is_active,
        "created_at": product.created_at,
        "updated_at": product.updated_at,
    }


def serialize_team_member(member: TeamMember) -> dict[str, object]:
    return {
        "id": member.id,
        "staff_id": member.staff_id,
        "name": member.name,
        "role": member.role,
        "team": member.team,
        "bill_rate": round_hours(member.bill_rate),
        "employment_type": member.employment_type,
        "contracting_company": member.contracting_company,
        "status": member.status,
        "created_at": member.created_at,
        "updated_at": member.updated_at,
    }


def serialize_month(month: FiscalMonth) -> dict[str, object]:
    return {
        "id": month.id,
        "fiscal_year": month.fiscal_year,
        "sequence": month.sequence,
        "label": month.label,
        "calendar_year": month.calendar_year,
        "calendar_month": month.calendar_month,
    }


def _forecast_entries(db: Session, fiscal_year: int, product_id: int | None = None) -> list[ForecastEntry]:
    statement = (
        select(ForecastEntry)
        .join(ForecastEntry.fiscal_month)
        .options(
            joinedload(ForecastEntry.product),
            joinedload(ForecastEntry.team_member),
            joinedload(ForecastEntry.bucket),
            joinedload(ForecastEntry.fiscal_month),
        )
        .where(FiscalMonth.fiscal_year == fiscal_year)
    )
    if product_id is not None:
        statement = statement.where(ForecastEntry.product_id == product_id)
    return list(db.scalars(statement))


def _actual_entries(db: Session, fiscal_year: int, product_id: int | None = None) -> list[ActualEntry]:
    statement = (
        select(ActualEntry)
        .join(ActualEntry.fiscal_month)
        .options(
            joinedload(ActualEntry.product),
            joinedload(ActualEntry.team_member),
            joinedload(ActualEntry.bucket),
            joinedload(ActualEntry.fiscal_month),
        )
        .where(FiscalMonth.fiscal_year == fiscal_year)
    )
    if product_id is not None:
        statement = statement.where(ActualEntry.product_id == product_id)
    return list(db.scalars(statement))


def _metric_totals(forecasts: list[ForecastEntry], actuals: list[ActualEntry]) -> dict[str, float]:
    forecast_hours = sum((entry.hours for entry in forecasts), Decimal("0"))
    actual_hours = sum((entry.hours for entry in actuals), Decimal("0"))
    forecast_cost = sum(calculate_cost(entry.hours, entry.team_member.bill_rate) for entry in forecasts)
    actual_cost = sum(calculate_cost(entry.hours, entry.team_member.bill_rate) for entry in actuals)

    return {
        "forecasted_hours": round_hours(forecast_hours),
        "forecasted_cost": round(forecast_cost, 2),
        "fytd_hours": round_hours(actual_hours),
        "fytd_cost": round(actual_cost, 2),
        "remaining_hours": round_hours(forecast_hours - actual_hours),
        "remaining_cost": round(forecast_cost - actual_cost, 2),
        "variance_hours": round_hours(actual_hours - forecast_hours),
        "variance_cost": round(actual_cost - forecast_cost, 2),
    }


def _budget_metrics(budget_amount: Decimal | float, projected_spend: Decimal | float) -> dict[str, float]:
    budget = Decimal(str(budget_amount or 0))
    projected = Decimal(str(projected_spend or 0))
    return {
        "budget_amount": round(float(budget), 2),
        "projected_spend": round(float(projected), 2),
        "budget_remaining": round(float(budget - projected), 2),
        "budget_utilization_percent": round(float((projected / budget * 100) if budget else Decimal("0")), 1),
    }


def dashboard_products(db: Session, fiscal_year: int) -> list[dict[str, object]]:
    products = db.scalars(select(Product).order_by(Product.name)).all()
    forecasts = _forecast_entries(db, fiscal_year)
    actuals = _actual_entries(db, fiscal_year)

    forecasts_by_product: dict[int, list[ForecastEntry]] = defaultdict(list)
    actuals_by_product: dict[int, list[ActualEntry]] = defaultdict(list)

    for entry in forecasts:
        forecasts_by_product[entry.product_id].append(entry)
    for entry in actuals:
        actuals_by_product[entry.product_id].append(entry)

    rows: list[dict[str, object]] = []
    for product in products:
        product_forecasts = forecasts_by_product[product.id]
        product_actuals = actuals_by_product[product.id]
        team_member_ids = {entry.team_member_id for entry in product_forecasts}
        team_member_ids.update(entry.team_member_id for entry in product_actuals)
        metrics = _metric_totals(product_forecasts, product_actuals)
        budget_metrics = _budget_metrics(product.budget_amount, metrics["forecasted_cost"])
        rows.append(
            {
                "product_id": product.id,
                "product": product.name,
                "jira_space_key": product.jira_space_key,
                "team_members": len(team_member_ids),
                **budget_metrics,
                **metrics,
                "forecast_consumed_percent": round(
                    (metrics["fytd_hours"] / metrics["forecasted_hours"] * 100)
                    if metrics["forecasted_hours"]
                    else 0,
                    1,
                ),
            }
        )
    return rows


def dashboard_summary(db: Session, fiscal_year: int) -> dict[str, float | int]:
    rows = dashboard_products(db, fiscal_year)
    summary = {
        "fiscal_year": fiscal_year,
        "product_count": len(rows),
        "team_member_count": db.scalar(select(func.count()).select_from(TeamMember).where(TeamMember.status == "active")) or 0,
    }
    for key in [
        "budget_amount",
        "projected_spend",
        "budget_remaining",
        "forecasted_hours",
        "forecasted_cost",
        "fytd_hours",
        "fytd_cost",
        "remaining_hours",
        "remaining_cost",
        "variance_hours",
        "variance_cost",
    ]:
        summary[key] = round(sum(float(row[key]) for row in rows), 2)
    summary["budget_utilization_percent"] = round(
        (summary["projected_spend"] / summary["budget_amount"] * 100) if summary["budget_amount"] else 0,
        1,
    )
    return summary


def product_summary(db: Session, product_id: int, fiscal_year: int) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise ValueError("Product not found")
    forecasts = _forecast_entries(db, fiscal_year, product_id)
    actuals = _actual_entries(db, fiscal_year, product_id)
    metrics = _metric_totals(forecasts, actuals)
    return {
        "product": serialize_product(product),
        "fiscal_year": fiscal_year,
        **_budget_metrics(product.budget_amount, metrics["forecasted_cost"]),
        **metrics,
    }


def bucket_distribution(db: Session, product_id: int, fiscal_year: int) -> list[dict[str, object]]:
    actuals = _actual_entries(db, fiscal_year, product_id)
    by_bucket: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    buckets_by_id: dict[int, Bucket] = {}
    for entry in actuals:
        by_bucket[entry.bucket_id] += entry.hours
        buckets_by_id[entry.bucket_id] = entry.bucket

    buckets = db.scalars(select(Bucket).order_by(Bucket.id)).all()
    rows = []
    for bucket in buckets:
        hours = by_bucket.get(bucket.id, Decimal("0"))
        rows.append({"bucket_id": bucket.id, "bucket": bucket.name, "code": bucket.code, "hours": round_hours(hours)})
    return rows


def product_bucket_tables(db: Session, product_id: int, fiscal_year: int) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise ValueError("Product not found")
    months = ensure_fiscal_months(db, fiscal_year)
    buckets = db.scalars(select(Bucket).order_by(Bucket.id)).all()
    forecasts = _forecast_entries(db, fiscal_year, product_id)
    actuals = _actual_entries(db, fiscal_year, product_id)

    forecast_by_key: dict[tuple[int, int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    actual_by_key: dict[tuple[int, int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    member_ids_by_bucket: dict[int, set[int]] = defaultdict(set)

    for entry in forecasts:
        key = (entry.bucket_id, entry.team_member_id, entry.fiscal_month_id)
        forecast_by_key[key] += entry.hours
        member_ids_by_bucket[entry.bucket_id].add(entry.team_member_id)
    for entry in actuals:
        key = (entry.bucket_id, entry.team_member_id, entry.fiscal_month_id)
        actual_by_key[key] += entry.hours
        member_ids_by_bucket[entry.bucket_id].add(entry.team_member_id)

    members_by_id = {member.id: member for member in db.scalars(select(TeamMember).order_by(TeamMember.name)).all()}
    bucket_payloads = []

    for bucket in buckets:
        rows = []
        bucket_totals = _empty_totals()
        for member_id in sorted(member_ids_by_bucket[bucket.id], key=lambda value: members_by_id[value].name):
            member = members_by_id[member_id]
            month_cells = []
            row_totals = _empty_totals()
            for month in months:
                forecast_hours = forecast_by_key[(bucket.id, member_id, month.id)]
                actual_hours = actual_by_key[(bucket.id, member_id, month.id)]
                cell = _cell_metrics(forecast_hours, actual_hours, member.bill_rate)
                month_cells.append({"fiscal_month_id": month.id, "sequence": month.sequence, "label": month.label, **cell})
                _add_totals(row_totals, cell)
                _add_totals(bucket_totals, cell)
            rows.append(
                {
                    "team_member_id": member.id,
                    "team_member": member.name,
                    "bill_rate": round_hours(member.bill_rate),
                    "months": month_cells,
                    "totals": _rounded_totals(row_totals),
                }
            )
        bucket_payloads.append(
            {
                "bucket_id": bucket.id,
                "code": bucket.code,
                "name": bucket.name,
                "rows": rows,
                "totals": _rounded_totals(bucket_totals),
            }
        )

    return {
        "product": serialize_product(product),
        "fiscal_year": fiscal_year,
        "months": [serialize_month(month) for month in months],
        "buckets": bucket_payloads,
    }


def team_member_products(db: Session, team_member_id: int, fiscal_year: int) -> dict[str, object]:
    member = db.get(TeamMember, team_member_id)
    if member is None:
        raise ValueError("Team member not found")
    forecasts = [entry for entry in _forecast_entries(db, fiscal_year) if entry.team_member_id == team_member_id]
    actuals = [entry for entry in _actual_entries(db, fiscal_year) if entry.team_member_id == team_member_id]
    grouped: dict[tuple[int, int], dict[str, object]] = {}

    for entry in forecasts:
        key = (entry.product_id, entry.bucket_id)
        grouped.setdefault(
            key,
            {"product": entry.product, "bucket": entry.bucket, "forecast_hours": Decimal("0"), "actual_hours": Decimal("0")},
        )
        grouped[key]["forecast_hours"] += entry.hours
    for entry in actuals:
        key = (entry.product_id, entry.bucket_id)
        grouped.setdefault(
            key,
            {"product": entry.product, "bucket": entry.bucket, "forecast_hours": Decimal("0"), "actual_hours": Decimal("0")},
        )
        grouped[key]["actual_hours"] += entry.hours

    rows = []
    product_budgets: dict[int, Decimal] = {}
    for values in grouped.values():
        product = values["product"]
        bucket = values["bucket"]
        product_budgets[product.id] = product.budget_amount or Decimal("0")
        forecast_hours = values["forecast_hours"]
        actual_hours = values["actual_hours"]
        forecast_cost = calculate_cost(forecast_hours, member.bill_rate)
        actual_cost = calculate_cost(actual_hours, member.bill_rate)
        rows.append(
            {
                "product_id": product.id,
                "product": product.name,
                "bucket_id": bucket.id,
                "bucket": bucket.name,
                "forecast_hours": round_hours(forecast_hours),
                "actual_hours": round_hours(actual_hours),
                "forecast_cost": forecast_cost,
                "actual_cost": actual_cost,
                "remaining_cost": round(forecast_cost - actual_cost, 2),
            }
        )
    projected_spend = sum(float(row["forecast_cost"]) for row in rows)
    return {
        "team_member": serialize_team_member(member),
        "fiscal_year": fiscal_year,
        **_budget_metrics(sum(product_budgets.values(), Decimal("0")), projected_spend),
        "products": rows,
    }


def _cell_metrics(forecast_hours: Decimal, actual_hours: Decimal, bill_rate: Decimal) -> dict[str, float]:
    forecast_cost = calculate_cost(forecast_hours, bill_rate)
    actual_cost = calculate_cost(actual_hours, bill_rate)
    return {
        "forecast_hours": round_hours(forecast_hours),
        "actual_hours": round_hours(actual_hours),
        "forecast_cost": forecast_cost,
        "actual_cost": actual_cost,
        "remaining_hours": round_hours(forecast_hours - actual_hours),
        "variance_hours": round_hours(actual_hours - forecast_hours),
        "remaining_cost": round(forecast_cost - actual_cost, 2),
        "variance_cost": round(actual_cost - forecast_cost, 2),
    }


def _empty_totals() -> dict[str, float]:
    return {
        "forecast_hours": 0,
        "actual_hours": 0,
        "forecast_cost": 0,
        "actual_cost": 0,
        "remaining_hours": 0,
        "variance_hours": 0,
        "remaining_cost": 0,
        "variance_cost": 0,
    }


def _add_totals(target: dict[str, float], values: dict[str, float]) -> None:
    for key in target:
        target[key] += values[key]


def _rounded_totals(values: dict[str, float]) -> dict[str, float]:
    return {key: round(value, 2) for key, value in values.items()}
