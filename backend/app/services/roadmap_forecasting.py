from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Bucket,
    FiscalMonth,
    ForecastEntry,
    Product,
    ProductTeamMember,
    RoadmapForecastAllocation,
    RoadmapItem,
    RoadmapItemIssueLink,
    TeamMember,
)
from app.services.aggregations import serialize_team_member
from app.services.costs import round_hours
from app.services.fiscal_year import ensure_fiscal_months, get_fiscal_month
from app.services.forecasting import upsert_forecast_entry
from app.services.roadmap import _is_roadmap_item_issue_type, roadmap_actual_rows
from app.services.slugs import product_url_slug, slugify, team_member_url_slug


def team_roadmap_forecast_plan(db: Session, team_ref: str, fiscal_year: int) -> dict[str, object]:
    team_name = resolve_team_name(db, team_ref)
    months = ensure_fiscal_months(db, fiscal_year)
    team_members = _team_members(db, team_name)
    rows = _planner_rows(db, team_name, fiscal_year)
    _attach_allocations(db, rows, fiscal_year)
    _attach_actuals(db, rows, fiscal_year)

    return {
        "team": team_name,
        "fiscal_year": fiscal_year,
        "months": [_serialize_month(month) for month in months],
        "team_members": [serialize_team_member(member) for member in team_members],
        "rows": sorted(rows.values(), key=_planner_row_sort_key),
    }


def upsert_team_roadmap_forecast_allocations(
    db: Session,
    team_ref: str,
    fiscal_year: int,
    entries: list[dict[str, object]],
) -> dict[str, object]:
    team_name = resolve_team_name(db, team_ref)
    affected_forecast_cells: set[tuple[int, int, int, int]] = set()

    for entry in entries:
        allocation, affected_cell = _upsert_allocation(db, team_name, fiscal_year, entry)
        if allocation is not None:
            affected_forecast_cells.add(_forecast_cell_key(allocation))
        if affected_cell is not None:
            affected_forecast_cells.add(affected_cell)

    for product_id, team_member_id, bucket_id, fiscal_month_id in sorted(affected_forecast_cells):
        _sync_forecast_cell_from_allocations(
            db,
            product_id=product_id,
            team_member_id=team_member_id,
            bucket_id=bucket_id,
            fiscal_month_id=fiscal_month_id,
        )

    db.flush()
    return team_roadmap_forecast_plan(db, team_name, fiscal_year)


def resolve_team_name(db: Session, team_ref: str) -> str:
    clean_ref = (team_ref or "").strip()
    ref_slug = slugify(clean_ref, fallback="team")
    teams = sorted({(member.team or "").strip() for member in db.scalars(select(TeamMember)).all() if (member.team or "").strip()})
    for team in teams:
        if slugify(team, fallback="team") == ref_slug:
            return team
    return clean_ref.replace("-", " ").strip() or "Unassigned"


def _upsert_allocation(
    db: Session,
    team_name: str,
    fiscal_year: int,
    entry: dict[str, object],
) -> tuple[RoadmapForecastAllocation | None, tuple[int, int, int, int] | None]:
    roadmap_item_id = int(entry["roadmap_item_id"])
    product_id = int(entry["product_id"])
    team_member_id = int(entry["team_member_id"])
    bucket_id = int(entry["bucket_id"])
    entry_fiscal_year = int(entry["fiscal_year"])
    month_sequence = int(entry["month_sequence"])
    hours = Decimal(str(entry["hours"]))
    if hours < 0:
        raise ValueError("Roadmap forecast hours must be zero or greater")
    if entry_fiscal_year != fiscal_year:
        raise ValueError("Roadmap forecast fiscal year does not match the selected fiscal year")

    item = db.get(RoadmapItem, roadmap_item_id)
    if item is None or item.fiscal_year != fiscal_year or not _is_roadmap_item_issue_type(item.issue_type):
        raise ValueError("Roadmap Item is not available for this fiscal year")
    product = db.get(Product, product_id)
    if product is None:
        raise ValueError("Product not found")
    bucket = db.get(Bucket, bucket_id)
    if bucket is None:
        raise ValueError("Bucket not found")
    if not _roadmap_context_matches(item, product.id, bucket.id):
        raise ValueError("Roadmap Item is not mapped to that Product and Bucket")
    member = db.get(TeamMember, team_member_id)
    if member is None:
        raise ValueError("Team Member not found")
    if slugify(member.team, fallback="team") != slugify(team_name, fallback="team"):
        raise ValueError("Team Member does not belong to this team")

    month = get_fiscal_month(db, fiscal_year, month_sequence)
    allocation = db.scalar(
        select(RoadmapForecastAllocation).where(
            RoadmapForecastAllocation.roadmap_item_id == item.id,
            RoadmapForecastAllocation.product_id == product.id,
            RoadmapForecastAllocation.team_member_id == member.id,
            RoadmapForecastAllocation.bucket_id == bucket.id,
            RoadmapForecastAllocation.fiscal_month_id == month.id,
        )
    )
    affected_cell = None if allocation is None else _forecast_cell_key(allocation)

    if hours == 0:
        if allocation is not None:
            db.delete(allocation)
        db.flush()
        return None, affected_cell or (product.id, member.id, bucket.id, month.id)

    if allocation is None:
        allocation = RoadmapForecastAllocation(
            roadmap_item_id=item.id,
            product_id=product.id,
            team_member_id=member.id,
            bucket_id=bucket.id,
            fiscal_month_id=month.id,
        )
        db.add(allocation)
    allocation.hours = hours
    db.flush()
    return allocation, affected_cell


def _sync_forecast_cell_from_allocations(
    db: Session,
    *,
    product_id: int,
    team_member_id: int,
    bucket_id: int,
    fiscal_month_id: int,
) -> ForecastEntry:
    total = db.scalar(
        select(func.coalesce(func.sum(RoadmapForecastAllocation.hours), Decimal("0")))
        .where(
            RoadmapForecastAllocation.product_id == product_id,
            RoadmapForecastAllocation.team_member_id == team_member_id,
            RoadmapForecastAllocation.bucket_id == bucket_id,
            RoadmapForecastAllocation.fiscal_month_id == fiscal_month_id,
        )
    )
    return upsert_forecast_entry(
        db,
        product_id=product_id,
        team_member_id=team_member_id,
        bucket_id=bucket_id,
        fiscal_month_id=fiscal_month_id,
        hours=Decimal(str(total or 0)),
    )


def _planner_rows(db: Session, team_name: str, fiscal_year: int) -> dict[tuple[int, int | None, int | None], dict[str, object]]:
    team_slug = slugify(team_name, fallback="team")
    team_product_ids = _product_ids_for_team(db, team_name)
    statement = (
        select(RoadmapItem)
        .options(
            joinedload(RoadmapItem.product),
            joinedload(RoadmapItem.bucket),
            joinedload(RoadmapItem.issue_links).joinedload(RoadmapItemIssueLink.product),
            joinedload(RoadmapItem.issue_links).joinedload(RoadmapItemIssueLink.bucket),
        )
        .where(RoadmapItem.fiscal_year == fiscal_year)
        .order_by(RoadmapItem.jira_issue_key)
    )
    rows: dict[tuple[int, int | None, int | None], dict[str, object]] = {}
    for item in db.scalars(statement).unique().all():
        if not _is_roadmap_item_issue_type(item.issue_type):
            continue
        source_team_matches = bool(item.source_team and slugify(item.source_team, fallback="team") == team_slug)
        for product, bucket in _roadmap_contexts(item):
            fallback_team_product = product is not None and product.id in team_product_ids
            if not source_team_matches and not fallback_team_product:
                continue
            key = (item.id, product.id if product else None, bucket.id if bucket else None)
            rows[key] = _serialize_planner_row(item, product, bucket, source_team_matches)
    return rows


def _product_ids_for_team(db: Session, team_name: str) -> set[int]:
    team_slug = slugify(team_name, fallback="team")
    return {
        assignment.product_id
        for assignment in db.scalars(
            select(ProductTeamMember)
            .join(ProductTeamMember.team_member)
            .where(ProductTeamMember.status == "active")
        ).all()
        if assignment.team_member.status == "active" and slugify(assignment.team_member.team, fallback="team") == team_slug
    }


def _roadmap_contexts(item: RoadmapItem) -> list[tuple[Product | None, Bucket | None]]:
    linked_contexts = [
        (link.product, link.bucket or item.bucket)
        for link in item.issue_links
        if link.product is not None or link.bucket is not None
    ]
    contexts = linked_contexts or [(item.product, item.bucket)]
    deduped: dict[tuple[int | None, int | None], tuple[Product | None, Bucket | None]] = {}
    for product, bucket in contexts:
        deduped[(product.id if product else None, bucket.id if bucket else None)] = (product, bucket)
    return list(deduped.values())


def _roadmap_context_matches(item: RoadmapItem, product_id: int, bucket_id: int) -> bool:
    return any(product is not None and bucket is not None and product.id == product_id and bucket.id == bucket_id for product, bucket in _roadmap_contexts(item))


def _attach_allocations(db: Session, rows: dict[tuple[int, int | None, int | None], dict[str, object]], fiscal_year: int) -> None:
    if not rows:
        return
    item_ids = {key[0] for key in rows}
    allocations = db.scalars(
        select(RoadmapForecastAllocation)
        .join(RoadmapForecastAllocation.fiscal_month)
        .options(
            joinedload(RoadmapForecastAllocation.team_member),
            joinedload(RoadmapForecastAllocation.fiscal_month),
        )
        .where(RoadmapForecastAllocation.roadmap_item_id.in_(item_ids), FiscalMonth.fiscal_year == fiscal_year)
    ).all()
    for allocation in allocations:
        key = (allocation.roadmap_item_id, allocation.product_id, allocation.bucket_id)
        row = rows.get(key)
        if row is None:
            continue
        row["forecast_hours"] += allocation.hours
        row["allocations"].append(_serialize_allocation(allocation))


def _attach_actuals(db: Session, rows: dict[tuple[int, int | None, int | None], dict[str, object]], fiscal_year: int) -> None:
    if not rows:
        return
    for actual in roadmap_actual_rows(db, fiscal_year):
        roadmap_item_id = actual["roadmap_item_id"]
        if roadmap_item_id is None:
            continue
        key = (int(roadmap_item_id), int(actual["product_id"]), int(actual["bucket_id"]))
        row = rows.get(key)
        if row is None:
            continue
        row["actual_hours"] += Decimal(str(actual["actual_hours"]))
        row["worklog_count"] += int(actual["worklog_count"])
        row["ticket_count"] += int(actual["ticket_count"])


def _team_members(db: Session, team_name: str) -> list[TeamMember]:
    team_slug = slugify(team_name, fallback="team")
    return [
        member
        for member in db.scalars(select(TeamMember).order_by(TeamMember.name)).all()
        if member.status == "active" and slugify(member.team, fallback="team") == team_slug
    ]


def _serialize_planner_row(item: RoadmapItem, product: Product | None, bucket: Bucket | None, source_team_matches: bool) -> dict[str, object]:
    return {
        "roadmap_item_id": item.id,
        "roadmap_item_key": item.jira_issue_key,
        "roadmap_item_title": item.title,
        "roadmap_item_status": item.status,
        "source_team": item.source_team,
        "source_team_matches": source_team_matches,
        "program_area": item.program_area,
        "roadmap_start_date": item.roadmap_start_date,
        "roadmap_end_date": item.roadmap_end_date,
        "source_url": item.source_url,
        "product_id": product.id if product else None,
        "product": product.name if product else None,
        "product_slug": product_url_slug(product) if product else None,
        "bucket_id": bucket.id if bucket else None,
        "bucket": bucket.name if bucket else None,
        "deliverables": [_serialize_deliverable_link(link, item) for link in _planner_component_links(item)],
        "forecast_hours": Decimal("0"),
        "actual_hours": Decimal("0"),
        "worklog_count": 0,
        "ticket_count": 0,
        "allocations": [],
    }


def _planner_component_links(item: RoadmapItem) -> list[RoadmapItemIssueLink]:
    return sorted(item.issue_links, key=lambda item_link: item_link.jira_issue_key)


def _serialize_deliverable_link(link: RoadmapItemIssueLink, item: RoadmapItem) -> dict[str, object]:
    effective_bucket = link.bucket or item.bucket
    return {
        "id": link.id,
        "jira_issue_id": link.jira_issue_id,
        "jira_issue_key": link.jira_issue_key,
        "jira_issue_summary": link.jira_issue_summary,
        "jira_project_key": link.jira_project_key,
        "product_id": link.product_id,
        "product": link.product.name if link.product else None,
        "product_slug": product_url_slug(link.product) if link.product else None,
        "bucket_id": effective_bucket.id if effective_bucket else None,
        "bucket": effective_bucket.name if effective_bucket else None,
        "status": link.status,
        "status_category": link.status_category,
        "source_category": link.source_category,
    }


def _serialize_allocation(allocation: RoadmapForecastAllocation) -> dict[str, object]:
    return {
        "id": allocation.id,
        "roadmap_item_id": allocation.roadmap_item_id,
        "product_id": allocation.product_id,
        "team_member_id": allocation.team_member_id,
        "team_member": allocation.team_member.name,
        "team_member_slug": team_member_url_slug(allocation.team_member),
        "bucket_id": allocation.bucket_id,
        "fiscal_month_id": allocation.fiscal_month_id,
        "month_sequence": allocation.fiscal_month.sequence,
        "hours": round_hours(allocation.hours),
    }


def _serialize_month(month: FiscalMonth) -> dict[str, object]:
    return {
        "id": month.id,
        "fiscal_year": month.fiscal_year,
        "sequence": month.sequence,
        "label": month.label,
        "calendar_year": month.calendar_year,
        "calendar_month": month.calendar_month,
    }


def _forecast_cell_key(allocation: RoadmapForecastAllocation) -> tuple[int, int, int, int]:
    return (allocation.product_id, allocation.team_member_id, allocation.bucket_id, allocation.fiscal_month_id)


def _planner_row_sort_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (str(row["product"] or "zz"), str(row["roadmap_item_key"]), str(row["bucket"] or "zz"))
