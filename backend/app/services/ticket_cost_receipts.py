from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import ActualEntry, Bucket, FiscalMonth, JiraTeamEstimationProfile, TeamMember
from app.services.costs import calculate_cost

DEVELOPER_TITLES = {"dev", "sr. dev"}


def product_ticket_cost_receipts(db: Session, product_id: int, fiscal_year: int) -> list[dict[str, object]]:
    entries = db.scalars(
        select(ActualEntry)
        .join(ActualEntry.fiscal_month)
        .options(joinedload(ActualEntry.team_member), joinedload(ActualEntry.fiscal_month), joinedload(ActualEntry.bucket))
        .where(ActualEntry.product_id == product_id, FiscalMonth.fiscal_year == fiscal_year)
        .order_by(FiscalMonth.sequence, ActualEntry.source_ticket_key, ActualEntry.id)
    ).all()
    profiles = {_key(p.jira_team): p for p in db.scalars(select(JiraTeamEstimationProfile).where(JiraTeamEstimationProfile.is_active.is_(True))).all()}
    rates = _role_rate_averages(db)
    grouped: dict[tuple[int, str], list[ActualEntry]] = defaultdict(list)
    for entry in entries:
        if entry.source_ticket_key:
            grouped[(entry.fiscal_month_id, entry.source_ticket_key)].append(entry)
    rows: list[dict[str, object]] = []
    for _, ticket_entries in grouped.items():
        first = ticket_entries[0]
        by_role: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"hours": Decimal("0"), "cost": Decimal("0")})
        work_type = _work_type(ticket_entries)
        for entry in ticket_entries:
            role = entry.team_member.role or "Unspecified"
            by_role[role]["hours"] += entry.hours
            by_role[role]["cost"] += Decimal(str(calculate_cost(entry.hours, entry.team_member.bill_rate)))
        actual_hours = sum((x["hours"] for x in by_role.values()), Decimal("0"))
        actual_cost = sum((x["cost"] for x in by_role.values()), Decimal("0"))
        estimated_cost, status = _estimated_cost(first.source_story_points, profiles.get(_key(first.source_team)), rates)
        rows.append({
            "fiscal_month_id": first.fiscal_month_id, "fiscal_month": first.fiscal_month.label, "month_sequence": first.fiscal_month.sequence,
            "ticket_key": first.source_ticket_key, "ticket_summary": first.source_ticket_summary or first.source_ticket_key,
            "work_type": work_type["label"], "work_type_code": work_type["code"],
            "jira_team": first.source_team, "story_points": float(first.source_story_points) if first.source_story_points is not None else None,
            "estimate_status": status, "estimated_cost": float(estimated_cost) if estimated_cost is not None else None,
            "actual_hours": float(actual_hours), "actual_cost": float(actual_cost),
            "variance_cost": float(actual_cost - estimated_cost) if estimated_cost is not None else None,
            "roles": [{"role": role, "actual_hours": float(value["hours"]), "actual_cost": float(value["cost"])} for role, value in sorted(by_role.items())],
        })
    return rows


def _role_rate_averages(db: Session) -> dict[str, Decimal]:
    rates: dict[str, list[Decimal]] = defaultdict(list)
    for member in db.scalars(select(TeamMember).where(TeamMember.status == "active")).all():
        title = (member.role or "").strip().casefold()
        if title in DEVELOPER_TITLES:
            rates["developer"].append(member.bill_rate)
        elif title == "qa":
            rates["qa"].append(member.bill_rate)
        elif title in {"product owner", "po"}:
            rates["product_owner"].append(member.bill_rate)
    return {role: sum(values, Decimal("0")) / len(values) for role, values in rates.items() if values}


def _estimated_cost(story_points: Decimal | None, profile: JiraTeamEstimationProfile | None, rates: dict[str, Decimal]) -> tuple[Decimal | None, str]:
    if profile is None:
        return None, "No Jira Team estimation profile"
    if story_points is None or story_points <= 0:
        return None, "No story points"
    if any(role not in rates for role in ("developer", "qa", "product_owner")):
        return None, "Missing active role rate"
    developer_hours = story_points / profile.velocity_story_points * profile.developer_capacity_hours
    total = developer_hours * rates["developer"] + developer_hours * profile.qa_percent_of_developer_hours * rates["qa"] + developer_hours * profile.product_owner_percent_of_developer_hours * rates["product_owner"]
    return total.quantize(Decimal("0.01")), "Estimated"


def _work_type(entries: list[ActualEntry]) -> dict[str, str]:
    buckets: dict[str, Bucket] = {}
    for entry in entries:
        if entry.bucket is not None:
            buckets[entry.bucket.code] = entry.bucket
    if len(buckets) == 1:
        bucket = next(iter(buckets.values()))
        return {"code": bucket.code, "label": bucket.name}
    if len(buckets) > 1:
        return {"code": "MIXED", "label": "Mixed"}
    return {"code": "UNCLASSIFIED", "label": "Unclassified"}


def _key(value: str | None) -> str:
    return (value or "").strip().casefold()
