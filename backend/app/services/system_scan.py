from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ActualEntry, FiscalMonth, ForecastEntry, Product, ProductBudget, TeamMember
from app.services.costs import calculate_cost, round_hours
from app.services.fiscal_year import fiscal_month_specs


@dataclass(frozen=True)
class ScanMonth:
    sequence: int
    label: str
    starts_on: date
    ends_on: date


def run_system_scan(
    db: Session,
    fiscal_year: int,
    *,
    as_of: date | None = None,
    budget_warning_percent: float = 85.0,
    member_forecast_limit_hours: float = 10.0,
    working_days: int = 7,
) -> dict[str, object]:
    scan_date = as_of or date.today()
    generated_at = datetime.now(timezone.utc)
    months = _scan_months(fiscal_year)
    current_month = _current_scan_month(months, scan_date)
    window_start = _subtract_working_days(scan_date, working_days)

    active_products = list(db.scalars(select(Product).where(Product.is_active.is_(True)).order_by(Product.name)))
    active_members = list(db.scalars(select(TeamMember).where(TeamMember.status == "active").order_by(TeamMember.name)))
    forecasts = _forecast_entries(db, fiscal_year)
    actuals = _actual_entries(db, fiscal_year)
    budgets = _product_budget_map(db, fiscal_year)

    forecast_hours_by_product_month: dict[tuple[int, int], Decimal] = defaultdict(_zero_decimal)
    forecast_hours_by_member_month: dict[tuple[int, int], Decimal] = defaultdict(_zero_decimal)
    forecast_cost_by_product: dict[int, float] = defaultdict(float)
    actual_cost_by_product: dict[int, float] = defaultdict(float)
    actual_hours_by_member_window: dict[int, Decimal] = defaultdict(_zero_decimal)
    current_forecast_by_member: dict[int, Decimal] = defaultdict(_zero_decimal)
    current_actual_by_member: dict[int, Decimal] = defaultdict(_zero_decimal)

    for entry in forecasts:
        month_sequence = entry.fiscal_month.sequence
        forecast_hours_by_product_month[(entry.product_id, month_sequence)] += entry.hours
        forecast_hours_by_member_month[(entry.team_member_id, month_sequence)] += entry.hours
        forecast_cost_by_product[entry.product_id] += calculate_cost(entry.hours, entry.team_member.bill_rate)
        if month_sequence == current_month.sequence:
            current_forecast_by_member[entry.team_member_id] += entry.hours

    for entry in actuals:
        actual_cost_by_product[entry.product_id] += calculate_cost(entry.hours, entry.team_member.bill_rate)
        if entry.worked_on is not None and window_start <= entry.worked_on <= scan_date:
            actual_hours_by_member_window[entry.team_member_id] += entry.hours
        if entry.fiscal_month.sequence == current_month.sequence:
            current_actual_by_member[entry.team_member_id] += entry.hours

    product_zeroes = _zero_forecast_by_month(active_products, months, forecast_hours_by_product_month)
    member_zeroes = _zero_forecast_by_month(active_members, months, forecast_hours_by_member_month)
    inactive_members = [member for member in active_members if actual_hours_by_member_window[member.id] <= 0]
    budget_alerts, products_without_budget = _budget_alerts(
        active_products,
        budgets,
        forecast_cost_by_product,
        actual_cost_by_product,
        budget_warning_percent,
    )
    member_limit_alerts = _member_limit_alerts(
        active_members,
        current_forecast_by_member,
        current_actual_by_member,
        member_forecast_limit_hours,
    )

    lines: list[str] = [
        "SPARC SYSTEM SCAN",
        f"Generated: {generated_at.isoformat()}",
        f"Fiscal year: FY{fiscal_year}",
        f"As of: {scan_date.isoformat()}",
        (
            "Parameters: "
            f"budget warning >= {budget_warning_percent:.1f}%, "
            f"member forecast buffer <= {_format_hours(member_forecast_limit_hours)} hours, "
            f"actual activity window = {working_days} working days"
        ),
        "",
        "SUMMARY",
        f"- Active products: {len(active_products)}",
        f"- Active team members: {len(active_members)}",
        f"- Forecast rows scanned: {len(forecasts)}",
        f"- Actual rows scanned: {len(actuals)}",
        f"- Current fiscal month basis: {current_month.label} ({current_month.starts_on.isoformat()} to {current_month.ends_on.isoformat()})",
        "",
    ]

    _append_grouped_zeroes(lines, "1. Products with zero forecasted hours by month", "product/month", product_zeroes)
    _append_grouped_zeroes(lines, "2. Team members with zero forecasted hours by month", "team-member/month", member_zeroes)
    _append_inactive_members(lines, inactive_members, actual_hours_by_member_window, window_start, scan_date, working_days)
    _append_budget_alerts(lines, budget_alerts, products_without_budget, budget_warning_percent)
    _append_member_limit_alerts(lines, member_limit_alerts, current_month, member_forecast_limit_hours)

    return {
        "fiscal_year": fiscal_year,
        "generated_at": generated_at,
        "output": "\n".join(lines),
    }


def _scan_months(fiscal_year: int) -> list[ScanMonth]:
    return [
        ScanMonth(
            sequence=int(spec["sequence"]),
            label=str(spec["label"]),
            starts_on=spec["starts_on"],
            ends_on=spec["ends_on"],
        )
        for spec in fiscal_month_specs(fiscal_year)
    ]


def _current_scan_month(months: list[ScanMonth], scan_date: date) -> ScanMonth:
    for month in months:
        if month.starts_on <= scan_date <= month.ends_on:
            return month
    if scan_date < months[0].starts_on:
        return months[0]
    return months[-1]


def _forecast_entries(db: Session, fiscal_year: int) -> list[ForecastEntry]:
    return list(
        db.scalars(
            select(ForecastEntry)
            .join(ForecastEntry.fiscal_month)
            .options(
                joinedload(ForecastEntry.product),
                joinedload(ForecastEntry.team_member),
                joinedload(ForecastEntry.fiscal_month),
            )
            .where(FiscalMonth.fiscal_year == fiscal_year)
        )
    )


def _actual_entries(db: Session, fiscal_year: int) -> list[ActualEntry]:
    return list(
        db.scalars(
            select(ActualEntry)
            .join(ActualEntry.fiscal_month)
            .options(
                joinedload(ActualEntry.product),
                joinedload(ActualEntry.team_member),
                joinedload(ActualEntry.fiscal_month),
            )
            .where(FiscalMonth.fiscal_year == fiscal_year)
        )
    )


def _product_budget_map(db: Session, fiscal_year: int) -> dict[int, Decimal]:
    return {
        product_id: budget_amount
        for product_id, budget_amount in db.execute(
            select(ProductBudget.product_id, ProductBudget.budget_amount).where(ProductBudget.fiscal_year == fiscal_year)
        )
    }


def _zero_forecast_by_month(
    items: list[Product] | list[TeamMember],
    months: list[ScanMonth],
    forecast_hours: dict[tuple[int, int], Decimal],
) -> list[tuple[str, list[str]]]:
    zeroes: list[tuple[str, list[str]]] = []
    for item in items:
        missing_months = [month.label for month in months if forecast_hours[(item.id, month.sequence)] <= 0]
        if missing_months:
            zeroes.append((item.name, missing_months))
    return zeroes


def _budget_alerts(
    products: list[Product],
    budgets: dict[int, Decimal],
    forecast_cost_by_product: dict[int, float],
    actual_cost_by_product: dict[int, float],
    budget_warning_percent: float,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    alerts: list[dict[str, object]] = []
    no_budget: list[dict[str, object]] = []

    for product in products:
        budget = budgets.get(product.id, Decimal("0"))
        forecast_cost = Decimal(str(forecast_cost_by_product[product.id]))
        actual_cost = Decimal(str(actual_cost_by_product[product.id]))
        if budget <= 0:
            if forecast_cost > 0 or actual_cost > 0:
                no_budget.append({"product": product.name, "forecast_cost": float(forecast_cost), "actual_cost": float(actual_cost)})
            continue

        forecast_percent = float(forecast_cost / budget * Decimal("100"))
        actual_percent = float(actual_cost / budget * Decimal("100"))
        alert_percent = max(forecast_percent, actual_percent)
        if alert_percent >= budget_warning_percent:
            alerts.append(
                {
                    "product": product.name,
                    "budget": float(budget),
                    "forecast_cost": float(forecast_cost),
                    "actual_cost": float(actual_cost),
                    "forecast_percent": forecast_percent,
                    "actual_percent": actual_percent,
                    "alert_percent": alert_percent,
                }
            )

    alerts.sort(key=lambda item: float(item["alert_percent"]), reverse=True)
    no_budget.sort(key=lambda item: str(item["product"]))
    return alerts, no_budget


def _member_limit_alerts(
    members: list[TeamMember],
    current_forecast_by_member: dict[int, Decimal],
    current_actual_by_member: dict[int, Decimal],
    member_forecast_limit_hours: float,
) -> list[dict[str, object]]:
    threshold = Decimal(str(member_forecast_limit_hours))
    alerts: list[dict[str, object]] = []

    for member in members:
        forecast_hours = current_forecast_by_member[member.id]
        actual_hours = current_actual_by_member[member.id]
        if forecast_hours <= 0 and actual_hours <= 0:
            continue
        remaining = forecast_hours - actual_hours
        if remaining <= threshold:
            alerts.append(
                {
                    "member": member.name,
                    "forecast_hours": forecast_hours,
                    "actual_hours": actual_hours,
                    "remaining_hours": remaining,
                }
            )

    alerts.sort(key=lambda item: Decimal(item["remaining_hours"]))
    return alerts


def _append_grouped_zeroes(lines: list[str], title: str, unit_label: str, grouped_zeroes: list[tuple[str, list[str]]]) -> None:
    lines.append(title.upper())
    total_gaps = sum(len(months) for _, months in grouped_zeroes)
    if not grouped_zeroes:
        lines.append(f"OK - No {unit_label} zero-forecast gaps found.")
        lines.append("")
        return

    lines.append(f"WARN - {total_gaps} {unit_label} zero-forecast gaps across {len(grouped_zeroes)} records.")
    for name, month_labels in grouped_zeroes[:75]:
        lines.append(f"- {name}: {', '.join(month_labels)}")
    if len(grouped_zeroes) > 75:
        lines.append(f"- ... {len(grouped_zeroes) - 75} more records omitted from console preview.")
    lines.append("")


def _append_inactive_members(
    lines: list[str],
    inactive_members: list[TeamMember],
    actual_hours_by_member_window: dict[int, Decimal],
    window_start: date,
    scan_date: date,
    working_days: int,
) -> None:
    lines.append(f"3. TEAM MEMBERS WITH NO ACTUAL HOURS IN THE PRIOR {working_days} WORKING DAYS")
    lines.append(f"Window: {window_start.isoformat()} to {scan_date.isoformat()}")
    if not inactive_members:
        lines.append("OK - Every active team member has actual hours in this window.")
        lines.append("")
        return

    lines.append(f"WARN - {len(inactive_members)} active team members have no actual hours in this window.")
    for member in inactive_members[:75]:
        hours = actual_hours_by_member_window[member.id]
        lines.append(f"- {member.name}: {_format_hours(hours)} hours")
    if len(inactive_members) > 75:
        lines.append(f"- ... {len(inactive_members) - 75} more records omitted from console preview.")
    lines.append("")


def _append_budget_alerts(
    lines: list[str],
    budget_alerts: list[dict[str, object]],
    products_without_budget: list[dict[str, object]],
    budget_warning_percent: float,
) -> None:
    lines.append("4. PRODUCTS NEARING BUDGET")
    if not budget_alerts and not products_without_budget:
        lines.append(f"OK - No active products are at or above {budget_warning_percent:.1f}% of budget.")
        lines.append("")
        return

    if budget_alerts:
        lines.append(f"WARN - {len(budget_alerts)} active products are at or above {budget_warning_percent:.1f}% of budget.")
        for alert in budget_alerts[:50]:
            lines.append(
                "- "
                f"{alert['product']}: "
                f"forecast {_format_currency(float(alert['forecast_cost']))} / budget {_format_currency(float(alert['budget']))} "
                f"({_format_percent(float(alert['forecast_percent']))}); "
                f"FYTD actual {_format_currency(float(alert['actual_cost']))} ({_format_percent(float(alert['actual_percent']))})"
            )
        if len(budget_alerts) > 50:
            lines.append(f"- ... {len(budget_alerts) - 50} more budget alerts omitted from console preview.")
    else:
        lines.append(f"OK - No active products are at or above {budget_warning_percent:.1f}% of budget.")

    if products_without_budget:
        lines.append(f"NOTE - {len(products_without_budget)} active products have spend but no FY budget set.")
        for product in products_without_budget[:25]:
            lines.append(
                "- "
                f"{product['product']}: "
                f"forecast {_format_currency(float(product['forecast_cost']))}; "
                f"FYTD actual {_format_currency(float(product['actual_cost']))}"
            )
        if len(products_without_budget) > 25:
            lines.append(f"- ... {len(products_without_budget) - 25} more no-budget products omitted from console preview.")
    lines.append("")


def _append_member_limit_alerts(
    lines: list[str],
    member_limit_alerts: list[dict[str, object]],
    current_month: ScanMonth,
    member_forecast_limit_hours: float,
) -> None:
    lines.append(f"5. TEAM MEMBERS WITHIN {_format_hours(member_forecast_limit_hours)} HOURS OF CURRENT-MONTH FORECAST")
    lines.append(f"Month: {current_month.label} ({current_month.starts_on.isoformat()} to {current_month.ends_on.isoformat()})")
    if not member_limit_alerts:
        lines.append("OK - No active team members are within the configured current-month forecast buffer.")
        lines.append("")
        return

    lines.append(f"WARN - {len(member_limit_alerts)} active team members are within the configured buffer or over forecast.")
    for alert in member_limit_alerts[:75]:
        remaining = Decimal(alert["remaining_hours"])
        if remaining < 0:
            status = f"over by {_format_hours(abs(remaining))} hours"
        else:
            status = f"{_format_hours(remaining)} hours remaining"
        lines.append(
            "- "
            f"{alert['member']}: "
            f"{_format_hours(Decimal(alert['actual_hours']))} actual / "
            f"{_format_hours(Decimal(alert['forecast_hours']))} forecast; "
            f"{status}"
        )
    if len(member_limit_alerts) > 75:
        lines.append(f"- ... {len(member_limit_alerts) - 75} more records omitted from console preview.")
    lines.append("")


def _subtract_working_days(value: date, working_days: int) -> date:
    cursor = value
    remaining = working_days
    while remaining > 0:
        cursor -= timedelta(days=1)
        if cursor.weekday() < 5:
            remaining -= 1
    return cursor


def _zero_decimal() -> Decimal:
    return Decimal("0")


def _format_hours(value: Decimal | int | float) -> str:
    formatted = f"{round_hours(value):,.1f}"
    return formatted.rstrip("0").rstrip(".")


def _format_currency(value: float) -> str:
    return f"${value:,.0f}"


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"
