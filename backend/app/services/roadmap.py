from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib
import re

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import (
    ActualEntry,
    Bucket,
    FiscalMonth,
    Product,
    ProductJiraSpace,
    RoadmapForecastAllocation,
    RoadmapItem,
    RoadmapItemIssueLink,
    SyncRun,
)
from app.services.costs import calculate_cost, round_hours
from app.services.estimation_policy import WORK_TYPE_ALIASES, normalize_lookup_value
from app.services.jira_projects import _raise_for_jira_response
from app.services.jira_rovo import _jira_field_text, _require_jira_settings, _search_jira_issues, serialize_sync_run
from app.services.slugs import product_url_slug, team_member_url_slug
from app.models.entities import utcnow

ROADMAP_SOURCE = "jira_product_discovery"
ROADMAP_LINK_SOURCE = "jira_issue_link"
MANUAL_ROADMAP_LINK_SOURCE = "manual"
DEFAULT_ROADMAP_PROJECT_KEY = "ROADMAP"
ROADMAP_ITEM_ISSUE_TYPES = {"idea"}
ROADMAP_DELIVERABLE_ISSUE_TYPES = {"deliverable"}
AGENCY_OFFICE_FIELD_NAMES = {"agency office"}
CATEGORY_FIELD_NAMES = {"category"}
TEAM_FIELD_NAMES = {"team"}
ROADMAP_RANGE_FIELD_NAMES = {
    "delivery dates",
    "delivery schedule",
    "delivery timeline",
    "project dates",
    "project schedule",
    "project timeline",
    "roadmap dates",
    "roadmap schedule",
    "roadmap timeline",
    "schedule",
    "target dates",
    "timeline",
    "timeframe",
}
ROADMAP_START_FIELD_NAMES = {
    *ROADMAP_RANGE_FIELD_NAMES,
    "begin",
    "begin date",
    "delivery start",
    "delivery start date",
    "planned start",
    "planned start date",
    "project start",
    "project start date",
    "roadmap start",
    "roadmap start date",
    "scheduled start",
    "scheduled start date",
    "start",
    "start date",
    "target start",
    "target start date",
}
ROADMAP_END_FIELD_NAMES = {
    *ROADMAP_RANGE_FIELD_NAMES,
    "completion",
    "completion date",
    "delivery due date",
    "delivery end",
    "delivery end date",
    "delivery target",
    "delivery target date",
    "due",
    "due date",
    "end",
    "end date",
    "finish",
    "finish date",
    "planned end",
    "planned end date",
    "project completion",
    "project completion date",
    "project due",
    "project due date",
    "project end",
    "project end date",
    "project finish",
    "project finish date",
    "project target",
    "project target date",
    "roadmap end",
    "roadmap end date",
    "scheduled end",
    "scheduled end date",
    "target",
    "target date",
    "target end",
    "target end date",
}
MONTH_NAME_LOOKUP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
MONTH_NAME_PATTERN = (
    r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
)
ROADMAP_CATEGORY_ALIASES = {
    **WORK_TYPE_ALIASES,
    "enhancements": "ENHANCE",
    "maint": "MAINTENANCE",
    "bugs": "MAINTENANCE",
}
UNSCOPED_ROADMAP_FISCAL_YEAR = 0


@dataclass(frozen=True)
class RoadmapIssueLinkPayload:
    issue_id: str | None
    issue_key: str
    issue_summary: str | None
    jira_project_key: str | None
    relationship_type: str | None
    issue_type: str | None = None
    status: str | None = None
    status_category: str | None = None
    category: str | None = None


@dataclass(frozen=True)
class RoadmapIssuePayload:
    issue_id: str
    issue_key: str
    title: str
    status: str | None
    status_category: str | None
    issue_type: str | None
    labels: tuple[str, ...]
    program_area: str | None
    category: str | None
    source_team: str | None
    source_url: str | None
    links: tuple[RoadmapIssueLinkPayload, ...]
    roadmap_start_date: date | None = None
    roadmap_end_date: date | None = None
    roadmap_schedule_months: tuple[int, ...] = tuple()


def serialize_roadmap_item(item: RoadmapItem, *, product_id: int | None = None) -> dict[str, object]:
    scoped_links = _scoped_roadmap_issue_links(item, product_id)
    return {
        "id": item.id,
        "source": item.source,
        "fiscal_year": item.fiscal_year,
        "product_id": item.product_id,
        "product": item.product.name if item.product else None,
        "product_slug": product_url_slug(item.product) if item.product else None,
        "bucket_id": item.bucket_id,
        "bucket": item.bucket.name if item.bucket else None,
        "jira_issue_id": item.jira_issue_id,
        "jira_issue_key": item.jira_issue_key,
        "title": item.title,
        "status": item.status,
        "status_category": item.status_category,
        "issue_type": item.issue_type,
        "program_area": item.program_area,
        "source_category": item.source_category,
        "source_team": item.source_team,
        "roadmap_start_date": item.roadmap_start_date,
        "roadmap_end_date": item.roadmap_end_date,
        "roadmap_schedule_months": item.roadmap_schedule_months or [],
        "source_url": item.source_url,
        "linked_issue_count": len(scoped_links),
        "linked_issues": [_serialize_roadmap_issue_link(link) for link in scoped_links],
        "forecast_hours": 0,
        "forecast_months": [],
        "forecast_team_member_count": 0,
        "last_synced_at": item.last_synced_at,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def list_roadmap_items(db: Session, fiscal_year: int | None = None) -> list[dict[str, object]]:
    statement = (
        select(RoadmapItem)
        .options(joinedload(RoadmapItem.product), joinedload(RoadmapItem.bucket), joinedload(RoadmapItem.issue_links))
        .order_by(RoadmapItem.jira_issue_key)
    )
    if fiscal_year is not None:
        statement = statement.where(RoadmapItem.fiscal_year == fiscal_year)
    items = db.scalars(
        statement
    ).unique().all()
    return [serialize_roadmap_item(item) for item in items if _is_roadmap_item_issue_type(item.issue_type)]


def product_roadmap_items(db: Session, product_id: int, fiscal_year: int) -> list[dict[str, object]]:
    direct_items = db.scalars(
        select(RoadmapItem)
        .options(joinedload(RoadmapItem.product), joinedload(RoadmapItem.bucket), joinedload(RoadmapItem.issue_links))
        .where(RoadmapItem.product_id == product_id, RoadmapItem.fiscal_year == fiscal_year)
        .order_by(RoadmapItem.jira_issue_key)
    ).unique().all()
    deliverable_parent_items = db.scalars(
        select(RoadmapItem)
        .join(RoadmapItem.issue_links)
        .options(joinedload(RoadmapItem.product), joinedload(RoadmapItem.bucket), joinedload(RoadmapItem.issue_links))
        .where(RoadmapItemIssueLink.product_id == product_id, RoadmapItem.fiscal_year == fiscal_year)
        .order_by(RoadmapItem.jira_issue_key)
    ).unique().all()
    deliverable_parent_items = [item for item in deliverable_parent_items if _has_product_linked_component(item, product_id)]
    items_by_id = {item.id: item for item in [*direct_items, *deliverable_parent_items]}
    items = sorted(items_by_id.values(), key=lambda item: item.jira_issue_key)
    serialized_items = [serialize_roadmap_item(item, product_id=product_id) for item in items if _is_roadmap_item_issue_type(item.issue_type)]
    _attach_product_roadmap_forecast_summaries(db, serialized_items, product_id, fiscal_year)
    return serialized_items


def _attach_product_roadmap_forecast_summaries(
    db: Session,
    serialized_items: list[dict[str, object]],
    product_id: int,
    fiscal_year: int,
) -> None:
    if not serialized_items:
        return

    item_ids = {int(item["id"]) for item in serialized_items}
    item_hours: defaultdict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    item_members: defaultdict[int, set[int]] = defaultdict(set)
    month_hours: defaultdict[tuple[int, int], Decimal] = defaultdict(lambda: Decimal("0"))
    month_members: defaultdict[tuple[int, int], set[int]] = defaultdict(set)
    month_labels: dict[tuple[int, int], str] = {}

    allocations = db.scalars(
        select(RoadmapForecastAllocation)
        .join(RoadmapForecastAllocation.fiscal_month)
        .options(joinedload(RoadmapForecastAllocation.fiscal_month))
        .where(
            RoadmapForecastAllocation.roadmap_item_id.in_(item_ids),
            RoadmapForecastAllocation.product_id == product_id,
            FiscalMonth.fiscal_year == fiscal_year,
        )
    ).all()
    for allocation in allocations:
        item_hours[allocation.roadmap_item_id] += allocation.hours
        item_members[allocation.roadmap_item_id].add(allocation.team_member_id)
        month_key = (allocation.roadmap_item_id, allocation.fiscal_month.sequence)
        month_hours[month_key] += allocation.hours
        month_members[month_key].add(allocation.team_member_id)
        month_labels[month_key] = allocation.fiscal_month.label

    for item in serialized_items:
        item_id = int(item["id"])
        item["forecast_hours"] = round_hours(item_hours[item_id])
        item["forecast_team_member_count"] = len(item_members[item_id])
        item["forecast_months"] = [
            {
                "month_sequence": month_sequence,
                "month_label": month_labels[(item_id, month_sequence)],
                "forecast_hours": round_hours(hours),
                "team_member_count": len(month_members[(item_id, month_sequence)]),
            }
            for (roadmap_item_id, month_sequence), hours in sorted(month_hours.items(), key=lambda entry: entry[0][1])
            if roadmap_item_id == item_id
        ]


def update_roadmap_item_mapping(
    db: Session,
    roadmap_item_id: int,
    *,
    product_id: int | None,
    bucket_id: int | None,
    program_area: str | None = None,
) -> dict[str, object]:
    item = db.get(RoadmapItem, roadmap_item_id)
    if item is None:
        raise ValueError("Roadmap Item not found")
    if product_id is not None and db.get(Product, product_id) is None:
        raise ValueError("Product not found")
    if bucket_id is not None and db.get(Bucket, bucket_id) is None:
        raise ValueError("Bucket not found")

    item.product_id = product_id
    item.bucket_id = bucket_id
    item.program_area = program_area.strip() if program_area else None
    db.flush()
    db.expire(item, ["product", "bucket", "issue_links"])
    mapped_item = db.scalars(
        select(RoadmapItem)
        .options(joinedload(RoadmapItem.product), joinedload(RoadmapItem.bucket), joinedload(RoadmapItem.issue_links))
        .where(RoadmapItem.id == roadmap_item_id)
    ).unique().one()
    return serialize_roadmap_item(mapped_item)


def roadmap_actual_gap_rows(db: Session, fiscal_year: int, *, month_sequence: int | None = None) -> list[dict[str, object]]:
    return [
        row
        for row in roadmap_actual_rows(db, fiscal_year, month_sequence=month_sequence)
        if row["mapping_status"] != "mapped"
    ]


def map_roadmap_ticket(db: Session, ticket_key: str, roadmap_item_id: int | None) -> dict[str, object]:
    normalized_ticket_key = _normalize_issue_key(ticket_key)
    if not normalized_ticket_key:
        raise ValueError("Ticket key is required")

    existing_links = db.scalars(select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == normalized_ticket_key)).all()
    for link in existing_links:
        db.delete(link)
    db.flush()

    if roadmap_item_id is None:
        return {
            "ticket_key": normalized_ticket_key,
            "roadmap_item_id": None,
            "roadmap_item_key": None,
            "roadmap_item_title": None,
        }

    item = db.get(RoadmapItem, roadmap_item_id)
    if item is None:
        raise ValueError("Roadmap Item not found")

    link = RoadmapItemIssueLink(
        roadmap_item_id=item.id,
        product_id=_product_id_from_project_key(db, _project_key_from_issue_key(normalized_ticket_key)),
        jira_issue_key=normalized_ticket_key,
        jira_project_key=_project_key_from_issue_key(normalized_ticket_key),
        source=MANUAL_ROADMAP_LINK_SOURCE,
        last_synced_at=utcnow(),
    )
    db.add(link)
    db.flush()
    return {
        "ticket_key": normalized_ticket_key,
        "roadmap_item_id": item.id,
        "roadmap_item_key": item.jira_issue_key,
        "roadmap_item_title": item.title,
    }


def run_live_roadmap_sync(db: Session, fiscal_year: int, roadmap_project_key: str = DEFAULT_ROADMAP_PROJECT_KEY) -> dict[str, object]:
    project_key = (roadmap_project_key or DEFAULT_ROADMAP_PROJECT_KEY).strip().upper()
    sync_run = SyncRun(source="jira_roadmap", mode="live", status="running")
    db.add(sync_run)
    db.flush()
    imported = 0
    linked = 0

    try:
        payloads = fetch_live_roadmap_items(project_key, fiscal_year)
        for payload in payloads:
            item = _upsert_roadmap_item(db, payload, fiscal_year)
            imported += 1
            linked += _replace_roadmap_issue_links(db, item, payload.links)
        removed = _remove_stale_roadmap_items_from_fiscal_year(db, fiscal_year, project_key, {payload.issue_key for payload in payloads})

        sync_run.status = "completed"
        sync_run.imported_count = imported
        sync_run.skipped_count = removed
        sync_run.completed_at = utcnow()
    except Exception as exc:
        sync_run.status = "failed"
        sync_run.imported_count = imported
        sync_run.skipped_count = linked
        sync_run.completed_at = utcnow()
        sync_run.error_summary = str(exc)
        raise

    db.flush()
    return {
        "source": "jira_roadmap",
        "sync_run": serialize_sync_run(sync_run),
        "roadmap_items": imported,
        "linked_issues": linked,
        "removed_from_fiscal_year": sync_run.skipped_count,
        "fiscal_year_label": _roadmap_fiscal_year_label(fiscal_year),
    }


def fetch_live_roadmap_items(roadmap_project_key: str, fiscal_year: int) -> list[RoadmapIssuePayload]:
    settings = get_settings()
    _require_jira_settings(settings.jira_site_url, settings.jira_api_email, settings.jira_api_token)
    site_url = settings.jira_site_url.rstrip("/")
    # Jira Product Discovery roadmap entries are Idea issues. Delivery tickets are linked underneath them.
    fiscal_year_label = _roadmap_fiscal_year_label(fiscal_year)
    jql = f'project = "{roadmap_project_key}" AND issuetype in ("Idea") AND labels = "{fiscal_year_label}" ORDER BY updated ASC'
    with httpx.Client(timeout=45, auth=(settings.jira_api_email, settings.jira_api_token)) as client:
        field_ids = _fetch_roadmap_field_ids(client, site_url)
        # Jira Product Discovery fields can be present in issue payloads even when the
        # field catalog does not expose them consistently. Roadmap issue volume is
        # small, so request all Idea fields and then extract the SPARC fields we need.
        fields = _unique_strings(
            [
                "*all",
                "summary",
                "labels",
                "status",
                "issuetype",
                "issuelinks",
                *field_ids["agency_office"],
                *field_ids["category"],
                *field_ids["team"],
                *field_ids["start_date"],
                *field_ids["end_date"],
            ]
        )
        issues = _search_jira_issues(client, site_url, jql, fields, expand=["names", "renderedFields"])
        payloads: list[RoadmapIssuePayload] = []
        for issue in issues:
            detailed_issue = _fetch_roadmap_issue_detail(client, site_url, issue)
            labels = _labels_from_issue(detailed_issue)
            if _is_roadmap_item_issue_type(_issue_type_name(detailed_issue)) and _has_fiscal_year_label(labels, fiscal_year):
                payloads.append(
                    _normalize_roadmap_issue(
                        site_url,
                        detailed_issue,
                        field_ids["agency_office"],
                        field_ids["category"],
                        field_ids["team"],
                        field_ids["start_date"],
                        field_ids["end_date"],
                        fiscal_year=fiscal_year,
                    )
                )
        return _enrich_roadmap_payload_links(client, site_url, payloads, field_ids["category"])


def _fetch_roadmap_issue_detail(client: httpx.Client, site_url: str, issue: dict[str, object]) -> dict[str, object]:
    issue_key = _normalize_issue_key(str(issue.get("key") or issue.get("id") or ""))
    if not issue_key:
        return issue
    try:
        response = client.get(
            f"{site_url.rstrip('/')}/rest/api/3/issue/{issue_key}",
            params={"fields": "*all", "expand": "names,renderedFields"},
            headers={"Accept": "application/json"},
        )
        _raise_for_jira_response(response)
    except (ValueError, httpx.HTTPError):
        return issue
    detail = response.json()
    if not isinstance(detail, dict):
        return issue
    return _merge_issue_detail(issue, detail)


def _merge_issue_detail(base: dict[str, object], detail: dict[str, object]) -> dict[str, object]:
    merged = {**base, **detail}
    for key in ("fields", "renderedFields", "names"):
        base_value = base.get(key) if isinstance(base.get(key), dict) else {}
        detail_value = detail.get(key) if isinstance(detail.get(key), dict) else {}
        merged[key] = {**base_value, **detail_value}
    return merged


def roadmap_actual_rows(
    db: Session,
    fiscal_year: int,
    *,
    product_id: int | None = None,
    team_member_id: int | None = None,
    bucket_id: int | None = None,
    month_sequence: int | None = None,
) -> list[dict[str, object]]:
    entries = _actual_entries(
        db,
        fiscal_year,
        product_id=product_id,
        team_member_id=team_member_id,
        bucket_id=bucket_id,
        month_sequence=month_sequence,
    )
    links_by_ticket = _roadmap_links_by_ticket(db, entries, fiscal_year)
    grouped: dict[tuple[int | None, int, int, int, str], dict[str, object]] = {}

    for entry in entries:
        ticket_key = _normalize_issue_key(entry.source_ticket_key or entry.source_issue_id)
        ticket_links = links_by_ticket.get(ticket_key, [])
        roadmap_item: RoadmapItem | None = None
        mapping_status = "unmapped"
        if len(ticket_links) == 1:
            roadmap_item = ticket_links[0].roadmap_item
            mapping_status = "mapped"
        elif len(ticket_links) > 1:
            mapping_status = "ambiguous"

        key = (roadmap_item.id if roadmap_item else None, entry.product_id, entry.team_member_id, entry.bucket_id, mapping_status)
        row = grouped.setdefault(
            key,
            {
                "roadmap_item_id": roadmap_item.id if roadmap_item else None,
                "roadmap_item_key": roadmap_item.jira_issue_key if roadmap_item else None,
                "roadmap_item_title": roadmap_item.title if roadmap_item else None,
                "roadmap_item_status": roadmap_item.status if roadmap_item else None,
                "program_area": roadmap_item.program_area if roadmap_item else None,
                "product_id": entry.product_id,
                "product": entry.product.name,
                "product_slug": product_url_slug(entry.product),
                "team_member_id": entry.team_member_id,
                "team_member": entry.team_member.name,
                "team_member_slug": team_member_url_slug(entry.team_member),
                "bucket_id": entry.bucket_id,
                "bucket": entry.bucket.name,
                "bucket_code": entry.bucket.code,
                "fiscal_year": fiscal_year,
                "actual_hours": Decimal("0"),
                "actual_cost": 0.0,
                "worklog_count": 0,
                "ticket_keys": set(),
                "mapping_status": mapping_status,
            },
        )
        row["actual_hours"] += entry.hours
        row["actual_cost"] = round(float(row["actual_cost"]) + calculate_cost(entry.hours, entry.team_member.bill_rate), 2)
        row["worklog_count"] += 1
        if ticket_key:
            row["ticket_keys"].add(ticket_key)

    rows = []
    for row in grouped.values():
        ticket_keys = sorted(row["ticket_keys"])
        rows.append(
            {
                **row,
                "actual_hours": round_hours(row["actual_hours"]),
                "ticket_count": len(ticket_keys),
                "ticket_keys": ticket_keys,
            }
        )
    return sorted(rows, key=_roadmap_actual_sort_key)


def _upsert_roadmap_item(db: Session, payload: RoadmapIssuePayload, fiscal_year: int) -> RoadmapItem:
    item = db.scalar(select(RoadmapItem).where(RoadmapItem.source == ROADMAP_SOURCE, RoadmapItem.jira_issue_id == payload.issue_id))
    if item is None:
        item = db.scalar(select(RoadmapItem).where(RoadmapItem.source == ROADMAP_SOURCE, RoadmapItem.jira_issue_key == payload.issue_key))
    if item is None:
        item = RoadmapItem(source=ROADMAP_SOURCE, jira_issue_id=payload.issue_id, jira_issue_key=payload.issue_key, title=payload.title)
        db.add(item)
    item.jira_issue_id = payload.issue_id
    item.jira_issue_key = payload.issue_key
    item.fiscal_year = fiscal_year
    item.title = payload.title
    item.status = payload.status
    item.status_category = payload.status_category
    item.issue_type = payload.issue_type
    if payload.program_area is not None:
        item.program_area = payload.program_area
    item.source_category = payload.category
    item.source_team = payload.source_team
    item.roadmap_start_date = payload.roadmap_start_date
    item.roadmap_end_date = payload.roadmap_end_date
    item.roadmap_schedule_months = list(payload.roadmap_schedule_months)
    bucket_id = _bucket_id_from_category(db, payload.category)
    if bucket_id is not None:
        item.bucket_id = bucket_id
    item.source_url = payload.source_url
    item.source_payload_hash = _roadmap_payload_hash(payload)
    item.last_synced_at = utcnow()
    inferred_product_id = _infer_product_id_from_links(db, payload.links)
    if inferred_product_id is not None and item.product_id is None:
        item.product_id = inferred_product_id
    db.flush()
    return item


def _remove_stale_roadmap_items_from_fiscal_year(
    db: Session,
    fiscal_year: int,
    roadmap_project_key: str,
    current_issue_keys: set[str],
) -> int:
    project_prefix = f"{roadmap_project_key.strip().upper()}-%"
    items = db.scalars(
        select(RoadmapItem).where(
            RoadmapItem.source == ROADMAP_SOURCE,
            RoadmapItem.fiscal_year == fiscal_year,
            RoadmapItem.jira_issue_key.like(project_prefix),
        )
    ).all()
    removed = 0
    for item in items:
        if item.jira_issue_key in current_issue_keys or not _is_roadmap_item_issue_type(item.issue_type):
            continue
        item.fiscal_year = UNSCOPED_ROADMAP_FISCAL_YEAR
        item.last_synced_at = utcnow()
        removed += 1
    db.flush()
    return removed


def _replace_roadmap_issue_links(db: Session, item: RoadmapItem, links: tuple[RoadmapIssueLinkPayload, ...]) -> int:
    existing = {link.jira_issue_key: link for link in item.issue_links}
    seen: set[str] = set()
    linked = 0
    now = utcnow()
    for payload in links:
        issue_key = _normalize_issue_key(payload.issue_key)
        if not issue_key or issue_key in seen or issue_key == item.jira_issue_key:
            continue
        seen.add(issue_key)
        link = existing.get(issue_key)
        if link is None:
            link = RoadmapItemIssueLink(roadmap_item_id=item.id, jira_issue_key=issue_key)
            db.add(link)
        link.jira_issue_id = payload.issue_id
        link.jira_issue_key = issue_key
        link.jira_issue_summary = payload.issue_summary
        link.jira_project_key = payload.jira_project_key
        link.product_id = _product_id_from_project_key(db, payload.jira_project_key)
        link.issue_type = payload.issue_type
        link.status = payload.status
        link.status_category = payload.status_category
        link.source_category = payload.category
        link.bucket_id = _bucket_id_from_category(db, payload.category) or item.bucket_id
        link.relationship_type = payload.relationship_type
        link.source = ROADMAP_LINK_SOURCE
        link.last_synced_at = now
        linked += 1

    stale_links = [link for key, link in existing.items() if key not in seen and link.source == ROADMAP_LINK_SOURCE]
    for link in stale_links:
        db.delete(link)
    db.flush()
    return linked


def _actual_entries(
    db: Session,
    fiscal_year: int,
    *,
    product_id: int | None = None,
    team_member_id: int | None = None,
    bucket_id: int | None = None,
    month_sequence: int | None = None,
) -> list[ActualEntry]:
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
        .order_by(ActualEntry.source_ticket_key, ActualEntry.id)
    )
    if product_id is not None:
        statement = statement.where(ActualEntry.product_id == product_id)
    if team_member_id is not None:
        statement = statement.where(ActualEntry.team_member_id == team_member_id)
    if bucket_id is not None:
        statement = statement.where(ActualEntry.bucket_id == bucket_id)
    if month_sequence is not None:
        statement = statement.where(FiscalMonth.sequence == month_sequence)
    return db.scalars(statement).all()


def _roadmap_links_by_ticket(db: Session, entries: list[ActualEntry], fiscal_year: int) -> dict[str, list[RoadmapItemIssueLink]]:
    ticket_keys = sorted(
        {
            ticket_key
            for entry in entries
            if (ticket_key := _normalize_issue_key(entry.source_ticket_key or entry.source_issue_id))
        }
    )
    if not ticket_keys:
        return {}
    links = db.scalars(
        select(RoadmapItemIssueLink)
        .options(joinedload(RoadmapItemIssueLink.roadmap_item))
        .where(RoadmapItemIssueLink.jira_issue_key.in_(ticket_keys))
        .order_by(RoadmapItemIssueLink.jira_issue_key, RoadmapItemIssueLink.roadmap_item_id)
    ).all()
    by_ticket: dict[str, list[RoadmapItemIssueLink]] = defaultdict(list)
    for link in links:
        if link.roadmap_item.fiscal_year != fiscal_year:
            continue
        if not _is_roadmap_item_issue_type(link.roadmap_item.issue_type):
            continue
        by_ticket[_normalize_issue_key(link.jira_issue_key)].append(link)
    return by_ticket


def _infer_product_id_from_links(db: Session, links: tuple[RoadmapIssueLinkPayload, ...]) -> int | None:
    project_keys = sorted({link.jira_project_key for link in links if link.jira_project_key})
    if not project_keys:
        return None
    product_ids = {
        product_id
        for product_id in db.scalars(
            select(ProductJiraSpace.product_id).where(
                ProductJiraSpace.jira_project_key.in_(project_keys),
                ProductJiraSpace.is_active.is_(True),
            )
        ).all()
        if product_id is not None
    }
    return next(iter(product_ids)) if len(product_ids) == 1 else None


def _product_id_from_project_key(db: Session, project_key: str | None) -> int | None:
    if not project_key:
        return None
    return db.scalar(
        select(ProductJiraSpace.product_id).where(
            ProductJiraSpace.jira_project_key == project_key.strip().upper(),
            ProductJiraSpace.is_active.is_(True),
        )
    )


def _normalize_roadmap_issue(
    site_url: str,
    issue: dict[str, object],
    agency_office_field_ids: list[str],
    category_field_ids: list[str],
    team_field_ids: list[str],
    start_date_field_ids: list[str] | None = None,
    end_date_field_ids: list[str] | None = None,
    fiscal_year: int = 2027,
) -> RoadmapIssuePayload:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    rendered_fields = issue.get("renderedFields") if isinstance(issue.get("renderedFields"), dict) else {}
    names = issue.get("names") if isinstance(issue.get("names"), dict) else {}
    status = fields.get("status") if isinstance(fields.get("status"), dict) else {}
    status_category = status.get("statusCategory") if isinstance(status.get("statusCategory"), dict) else {}
    issue_type = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
    issue_key = _normalize_issue_key(str(issue.get("key") or ""))
    links = tuple(_extract_issue_links(fields, issue_key, category_field_ids))
    labels = _labels_from_issue(issue)
    field_sources = [fields, rendered_fields]
    start_date_ids = _unique_strings([*(start_date_field_ids or []), *_roadmap_date_field_ids_from_issue_names(names, ROADMAP_START_FIELD_NAMES, role="start")])
    end_date_ids = _unique_strings([*(end_date_field_ids or []), *_roadmap_date_field_ids_from_issue_names(names, ROADMAP_END_FIELD_NAMES, role="end")])
    roadmap_start_date = _roadmap_date_from_issue_field_sources(
        field_sources,
        start_date_ids,
        preferred_keys=("start", "startDate", "from"),
        range_position="start",
    ) or _roadmap_date_from_any_issue_field_sources(field_sources, range_position="start")
    roadmap_start_range_end = _roadmap_date_from_issue_field_sources(
        field_sources,
        start_date_ids,
        preferred_keys=("end", "endDate", "target", "targetDate", "to", "start", "startDate", "from"),
        range_position="end",
    )
    roadmap_end_date = roadmap_start_range_end or _roadmap_date_from_issue_field_sources(
        field_sources,
        end_date_ids,
        preferred_keys=("end", "endDate", "target", "targetDate", "due", "dueDate", "to"),
        range_position="end",
    ) or _roadmap_date_from_any_issue_field_sources(field_sources, range_position="end")
    roadmap_schedule_months = _roadmap_schedule_months_from_issue_field_sources(
        field_sources,
        start_date_ids,
        end_date_ids,
        fiscal_year=fiscal_year,
    )
    return RoadmapIssuePayload(
        issue_id=str(issue.get("id") or issue_key),
        issue_key=issue_key,
        title=str(fields.get("summary") or issue_key),
        status=str(status.get("name") or "") or None,
        status_category=str(status_category.get("name") or "") or None,
        issue_type=str(issue_type.get("name") or "") or None,
        labels=labels,
        program_area=_program_area_from_issue_fields(fields, agency_office_field_ids),
        category=_category_from_issue_fields(fields, category_field_ids),
        source_team=_team_from_issue_fields(fields, team_field_ids),
        roadmap_start_date=roadmap_start_date,
        roadmap_end_date=roadmap_end_date,
        roadmap_schedule_months=roadmap_schedule_months,
        source_url=f"{site_url}/browse/{issue_key}" if issue_key else None,
        links=links,
    )


def _issue_type_name(issue: dict[str, object]) -> str | None:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    issue_type = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
    value = str(issue_type.get("name") or "").strip()
    return value or None


def _is_roadmap_item_issue_type(issue_type: str | None) -> bool:
    if issue_type is None:
        return True
    return issue_type.strip().lower() in ROADMAP_ITEM_ISSUE_TYPES


def _is_roadmap_deliverable_issue_type(issue_type: str | None) -> bool:
    if issue_type is None:
        return False
    return issue_type.strip().lower() in ROADMAP_DELIVERABLE_ISSUE_TYPES


def _has_product_linked_component(item: RoadmapItem, product_id: int) -> bool:
    return any(link.product_id == product_id for link in item.issue_links)


def _scoped_roadmap_issue_links(item: RoadmapItem, product_id: int | None) -> list[RoadmapItemIssueLink]:
    links = sorted(item.issue_links, key=lambda link: link.jira_issue_key)
    if product_id is None:
        return links
    deliverable_links = [
        link
        for link in links
        if link.product_id == product_id and _is_roadmap_deliverable_issue_type(link.issue_type)
    ]
    if deliverable_links:
        return deliverable_links
    product_links = [link for link in links if link.product_id == product_id]
    if product_links:
        return product_links
    return links if item.product_id == product_id else []


def _serialize_roadmap_issue_link(link: RoadmapItemIssueLink) -> dict[str, object]:
    return {
        "id": link.id,
        "jira_issue_id": link.jira_issue_id,
        "jira_issue_key": link.jira_issue_key,
        "jira_issue_summary": link.jira_issue_summary,
        "jira_project_key": link.jira_project_key,
        "product_id": link.product_id,
        "product": link.product.name if link.product else None,
        "product_slug": product_url_slug(link.product) if link.product else None,
        "bucket_id": link.bucket_id,
        "bucket": link.bucket.name if link.bucket else None,
        "issue_type": link.issue_type,
        "status": link.status,
        "status_category": link.status_category,
        "source_category": link.source_category,
        "relationship_type": link.relationship_type,
        "source": link.source,
        "last_synced_at": link.last_synced_at,
    }


def _extract_issue_links(fields: dict[str, object], roadmap_issue_key: str, category_field_ids: list[str]) -> list[RoadmapIssueLinkPayload]:
    raw_links = fields.get("issuelinks") if isinstance(fields, dict) else []
    if not isinstance(raw_links, list):
        return []
    links: list[RoadmapIssueLinkPayload] = []
    for raw_link in raw_links:
        if not isinstance(raw_link, dict):
            continue
        issue = raw_link.get("outwardIssue") if isinstance(raw_link.get("outwardIssue"), dict) else raw_link.get("inwardIssue")
        if not isinstance(issue, dict):
            continue
        issue_key = _normalize_issue_key(str(issue.get("key") or ""))
        if not issue_key or issue_key == roadmap_issue_key:
            continue
        link_type = raw_link.get("type") if isinstance(raw_link.get("type"), dict) else {}
        links.append(
            _roadmap_issue_link_payload_from_issue(
                issue,
                category_field_ids=category_field_ids,
                relationship_type=str(link_type.get("name") or "") or None,
            )
        )
    return links


def _enrich_roadmap_payload_links(
    client: httpx.Client,
    site_url: str,
    payloads: list[RoadmapIssuePayload],
    category_field_ids: list[str],
) -> list[RoadmapIssuePayload]:
    linked_issue_keys = sorted({link.issue_key for payload in payloads for link in payload.links if link.issue_key})
    if not linked_issue_keys:
        return payloads

    issue_details: dict[str, RoadmapIssueLinkPayload] = {}
    fields = ["summary", "status", "issuetype", "project", *category_field_ids]
    for key_chunk in _chunks(linked_issue_keys, 50):
        jql = f"issuekey in ({', '.join(key_chunk)})"
        for issue in _search_jira_issues(client, site_url, jql, fields):
            detail = _roadmap_issue_link_payload_from_issue(issue, category_field_ids=category_field_ids)
            issue_details[detail.issue_key] = detail

    enriched_payloads: list[RoadmapIssuePayload] = []
    for payload in payloads:
        enriched_links = tuple(_merge_link_details(link, issue_details.get(link.issue_key)) for link in payload.links)
        enriched_payloads.append(
            RoadmapIssuePayload(
                issue_id=payload.issue_id,
                issue_key=payload.issue_key,
                title=payload.title,
                status=payload.status,
                status_category=payload.status_category,
                issue_type=payload.issue_type,
                labels=payload.labels,
                program_area=payload.program_area,
                category=payload.category,
                source_team=payload.source_team,
                roadmap_start_date=payload.roadmap_start_date,
                roadmap_end_date=payload.roadmap_end_date,
                roadmap_schedule_months=payload.roadmap_schedule_months,
                source_url=payload.source_url,
                links=enriched_links,
            )
        )
    return enriched_payloads


def _roadmap_issue_link_payload_from_issue(
    issue: dict[str, object],
    *,
    category_field_ids: list[str],
    relationship_type: str | None = None,
) -> RoadmapIssueLinkPayload:
    issue_key = _normalize_issue_key(str(issue.get("key") or ""))
    issue_fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    project = issue_fields.get("project") if isinstance(issue_fields.get("project"), dict) else {}
    status = issue_fields.get("status") if isinstance(issue_fields.get("status"), dict) else {}
    status_category = status.get("statusCategory") if isinstance(status.get("statusCategory"), dict) else {}
    issue_type = issue_fields.get("issuetype") if isinstance(issue_fields.get("issuetype"), dict) else {}
    return RoadmapIssueLinkPayload(
        issue_id=str(issue.get("id") or "") or None,
        issue_key=issue_key,
        issue_summary=str(issue_fields.get("summary") or "") or None,
        jira_project_key=str(project.get("key") or "").upper() or _project_key_from_issue_key(issue_key),
        relationship_type=relationship_type,
        issue_type=str(issue_type.get("name") or "") or None,
        status=str(status.get("name") or "") or None,
        status_category=str(status_category.get("name") or "") or None,
        category=_category_from_issue_fields(issue_fields, category_field_ids),
    )


def _merge_link_details(base: RoadmapIssueLinkPayload, enriched: RoadmapIssueLinkPayload | None) -> RoadmapIssueLinkPayload:
    if enriched is None:
        return base
    return RoadmapIssueLinkPayload(
        issue_id=enriched.issue_id or base.issue_id,
        issue_key=base.issue_key,
        issue_summary=enriched.issue_summary or base.issue_summary,
        jira_project_key=enriched.jira_project_key or base.jira_project_key,
        relationship_type=base.relationship_type or enriched.relationship_type,
        issue_type=enriched.issue_type or base.issue_type,
        status=enriched.status or base.status,
        status_category=enriched.status_category or base.status_category,
        category=enriched.category or base.category,
    )


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


def _fetch_roadmap_field_ids(client: httpx.Client, site_url: str) -> dict[str, list[str]]:
    response = client.get(f"{site_url.rstrip('/')}/rest/api/3/field", headers={"Accept": "application/json"})
    _raise_for_jira_response(response)
    fields = response.json()
    if not isinstance(fields, list):
        return {"agency_office": [], "category": [], "team": [], "start_date": [], "end_date": []}
    return {
        "agency_office": _jira_field_ids_by_name(fields, AGENCY_OFFICE_FIELD_NAMES),
        "category": _jira_field_ids_by_name(fields, CATEGORY_FIELD_NAMES),
        "team": _jira_field_ids_by_name(fields, TEAM_FIELD_NAMES),
        "start_date": _jira_date_field_ids_by_name(fields, ROADMAP_START_FIELD_NAMES, role="start"),
        "end_date": _jira_date_field_ids_by_name(fields, ROADMAP_END_FIELD_NAMES, role="end"),
    }


def _jira_field_ids_by_name(fields: list[object], names: set[str]) -> list[str]:
    return [
        str(field["id"])
        for field in fields
        if isinstance(field, dict)
        and str(field.get("name") or "").strip().casefold() in names
        and field.get("id")
    ]


def _jira_date_field_ids_by_name(fields: list[object], names: set[str], *, role: str) -> list[str]:
    exact_matches = _jira_field_ids_by_name(fields, names)
    seen = set(exact_matches)
    fuzzy_matches: list[str] = []
    for field in fields:
        if not isinstance(field, dict) or not field.get("id"):
            continue
        field_id = str(field["id"])
        if field_id in seen:
            continue
        field_name = str(field.get("name") or "").strip()
        if _looks_like_roadmap_date_field(field_name, role=role):
            fuzzy_matches.append(field_id)
            seen.add(field_id)
    return [*exact_matches, *fuzzy_matches]


def _roadmap_date_field_ids_from_issue_names(names: dict[str, object], field_names: set[str], *, role: str) -> list[str]:
    fields = [
        {"id": field_id, "name": field_name}
        for field_id, field_name in names.items()
        if isinstance(field_id, str) and isinstance(field_name, str)
    ]
    return _jira_date_field_ids_by_name(fields, field_names, role=role)


def _looks_like_roadmap_date_field(field_name: str, *, role: str) -> bool:
    name = field_name.casefold()
    if not name:
        return False
    range_terms = (
        "delivery dates",
        "delivery schedule",
        "delivery timeline",
        "roadmap dates",
        "roadmap schedule",
        "roadmap timeline",
        "schedule",
        "target dates",
        "timeline",
        "timeframe",
    )
    if any(term in name for term in range_terms):
        return True
    context_terms = ("date", "delivery", "planned", "project", "roadmap", "schedule", "target", "timeline")
    if role == "start":
        role_terms = ("begin", "start")
    else:
        role_terms = ("completion", "due", "end", "finish", "target")
    return any(term in name for term in role_terms) and any(term in name for term in context_terms)


def _program_area_from_issue_fields(fields: dict[str, object], agency_office_field_ids: list[str]) -> str | None:
    for field_id in agency_office_field_ids:
        value = _jira_field_text(fields.get(field_id))
        if value:
            return value
    return None


def _category_from_issue_fields(fields: dict[str, object], category_field_ids: list[str]) -> str | None:
    for field_id in category_field_ids:
        value = _jira_field_text(fields.get(field_id))
        if value:
            return value
    return None


def _team_from_issue_fields(fields: dict[str, object], team_field_ids: list[str]) -> str | None:
    for field_id in team_field_ids:
        value = _jira_field_text(fields.get(field_id))
        if value:
            return value
    return None


def _roadmap_date_from_issue_fields(
    fields: dict[str, object],
    date_field_ids: list[str],
    *,
    preferred_keys: tuple[str, ...],
    range_position: str,
) -> date | None:
    for field_id in date_field_ids:
        parsed = _parse_jira_date(fields.get(field_id), preferred_keys=preferred_keys, range_position=range_position)
        if parsed is not None:
            return parsed
    return None


def _roadmap_date_from_issue_field_sources(
    field_sources: list[dict[str, object]],
    date_field_ids: list[str],
    *,
    preferred_keys: tuple[str, ...],
    range_position: str,
) -> date | None:
    for fields in field_sources:
        parsed = _roadmap_date_from_issue_fields(
            fields,
            date_field_ids,
            preferred_keys=preferred_keys,
            range_position=range_position,
        )
        if parsed is not None:
            return parsed
    return None


def _roadmap_date_from_any_issue_field(fields: dict[str, object], *, range_position: str) -> date | None:
    for raw_text in _jira_field_text_values(fields):
        if not re.search(MONTH_NAME_PATTERN, raw_text, flags=re.IGNORECASE) or not re.search(r"\b20\d{2}\b", raw_text):
            continue
        parsed = _parse_jira_text_date(raw_text, range_position=range_position)
        if parsed is not None:
            return parsed
    return None


def _roadmap_date_from_any_issue_field_sources(field_sources: list[dict[str, object]], *, range_position: str) -> date | None:
    for fields in field_sources:
        parsed = _roadmap_date_from_any_issue_field(fields, range_position=range_position)
        if parsed is not None:
            return parsed
    return None


def _roadmap_schedule_months_from_issue_field_sources(
    field_sources: list[dict[str, object]],
    start_date_ids: list[str],
    end_date_ids: list[str],
    *,
    fiscal_year: int,
) -> tuple[int, ...]:
    month_sequences: set[int] = set()
    date_field_ids = _unique_strings([*start_date_ids, *end_date_ids])
    for fields in field_sources:
        for field_id in date_field_ids:
            if field_id in fields:
                month_sequences.update(_roadmap_schedule_months_from_value(fields.get(field_id), fiscal_year=fiscal_year))

    if not month_sequences:
        for fields in field_sources:
            for raw_text in _jira_field_text_values(fields):
                if not re.search(MONTH_NAME_PATTERN, raw_text, flags=re.IGNORECASE) or not re.search(r"\b20\d{2}\b", raw_text):
                    continue
                month_sequences.update(_roadmap_schedule_months_from_value(raw_text, fiscal_year=fiscal_year))

    return tuple(sorted(month_sequences))


def _roadmap_schedule_months_from_value(value: object, *, fiscal_year: int) -> set[int]:
    if value is None:
        return set()
    if isinstance(value, datetime):
        sequence = _fiscal_month_sequence(value.date(), fiscal_year=fiscal_year)
        return {sequence} if sequence is not None else set()
    if isinstance(value, date):
        sequence = _fiscal_month_sequence(value, fiscal_year=fiscal_year)
        return {sequence} if sequence is not None else set()
    if isinstance(value, (list, tuple)):
        month_sequences: set[int] = set()
        for item in value:
            month_sequences.update(_roadmap_schedule_months_from_value(item, fiscal_year=fiscal_year))
        return month_sequences
    if isinstance(value, dict):
        month_sequences: set[int] = set()
        start = _parse_jira_date(value, preferred_keys=("start", "startDate", "from"), range_position="start")
        end = _parse_jira_date(
            value,
            preferred_keys=("end", "endDate", "target", "targetDate", "due", "dueDate", "to"),
            range_position="end",
        )
        if start is not None or end is not None:
            first = start or end
            last = end or start
            if first is not None and last is not None:
                month_sequences.update(_fiscal_month_sequences_between(first, last, fiscal_year=fiscal_year))
        for nested_value in value.values():
            month_sequences.update(_roadmap_schedule_months_from_value(nested_value, fiscal_year=fiscal_year))
        return month_sequences

    raw = re.sub(r"<[^>]+>", " ", str(value)).strip()
    if not raw:
        return set()

    month_sequences = _roadmap_schedule_months_from_text(raw, fiscal_year=fiscal_year)
    if month_sequences:
        return month_sequences

    start = _parse_jira_date(raw, range_position="start")
    end = _parse_jira_date(raw, range_position="end")
    if start is None and end is None:
        return set()
    first = start or end
    last = end or start
    if first is None or last is None:
        return set()
    return _fiscal_month_sequences_between(first, last, fiscal_year=fiscal_year)


def _roadmap_schedule_months_from_text(raw: str, *, fiscal_year: int) -> set[int]:
    normalized = raw.replace("\u2013", "-").replace("\u2014", "-")
    month_pattern = f"(?P<start>{MONTH_NAME_PATTERN})(?:\\s*-\\s*(?P<end>{MONTH_NAME_PATTERN}))?\\s*,?\\s*(?P<year>20\\d{{2}})"
    month_sequences: set[int] = set()
    for match in re.finditer(month_pattern, normalized, flags=re.IGNORECASE):
        start_month = MONTH_NAME_LOOKUP[match.group("start").casefold()]
        end_month = MONTH_NAME_LOOKUP[(match.group("end") or match.group("start")).casefold()]
        year = int(match.group("year"))
        month_sequences.update(_fiscal_month_sequences_for_named_range(start_month, end_month, year, fiscal_year=fiscal_year))
    return month_sequences


def _fiscal_month_sequences_for_named_range(start_month: int, end_month: int, year: int, *, fiscal_year: int) -> set[int]:
    if start_month <= end_month:
        return _fiscal_month_sequences_between(date(year, start_month, 1), date(year, end_month, _last_day_of_month(year, end_month)), fiscal_year=fiscal_year)

    start_year_candidates = {year, year - 1}
    month_sequences: set[int] = set()
    for start_year in start_year_candidates:
        end_year = start_year + 1
        month_sequences.update(
            _fiscal_month_sequences_between(
                date(start_year, start_month, 1),
                date(end_year, end_month, _last_day_of_month(end_year, end_month)),
                fiscal_year=fiscal_year,
            )
        )
    return month_sequences


def _fiscal_month_sequences_between(start: date, end: date, *, fiscal_year: int) -> set[int]:
    first = start if start <= end else end
    last = end if start <= end else start
    month_sequences: set[int] = set()
    current_year = first.year
    current_month = first.month
    while (current_year, current_month) <= (last.year, last.month):
        sequence = _fiscal_month_sequence(date(current_year, current_month, 1), fiscal_year=fiscal_year)
        if sequence is not None:
            month_sequences.add(sequence)
        if current_month == 12:
            current_year += 1
            current_month = 1
        else:
            current_month += 1
    return month_sequences


def _fiscal_month_sequence(value: date, *, fiscal_year: int) -> int | None:
    if value.year == fiscal_year - 1 and value.month >= 7:
        return value.month - 6
    if value.year == fiscal_year and value.month <= 6:
        return value.month + 6
    return None


def _jira_field_text_values(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (date, datetime)):
        return []
    if isinstance(value, (int, float, bool)):
        return []
    if isinstance(value, dict):
        values: list[str] = []
        for nested_value in value.values():
            values.extend(_jira_field_text_values(nested_value))
        return values
    if isinstance(value, (list, tuple)):
        values: list[str] = []
        for nested_value in value:
            values.extend(_jira_field_text_values(nested_value))
        return values
    return []


def _parse_jira_date(value: object, *, preferred_keys: tuple[str, ...] = tuple(), range_position: str = "start") -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (list, tuple)):
        for item in value:
            parsed = _parse_jira_date(item, preferred_keys=preferred_keys, range_position=range_position)
            if parsed is not None:
                return parsed
        return None
    if isinstance(value, dict):
        keys = (
            *preferred_keys,
            "value",
            "date",
            "start",
            "startDate",
            "begin",
            "beginDate",
            "end",
            "endDate",
            "target",
            "targetDate",
            "due",
            "dueDate",
        )
        normalized_values = {_normalize_jira_field_key(str(key)): nested_value for key, nested_value in value.items()}
        for key in keys:
            normalized_key = _normalize_jira_field_key(key)
            if normalized_key not in normalized_values:
                continue
            parsed = _parse_jira_date(normalized_values[normalized_key], preferred_keys=preferred_keys, range_position=range_position)
            if parsed is not None:
                return parsed
        for nested_value in value.values():
            parsed = _parse_jira_date(nested_value, preferred_keys=preferred_keys, range_position=range_position)
            if parsed is not None:
                return parsed
        return None
    raw = str(value).strip()
    if not raw:
        return None
    parsed_text_date = _parse_jira_text_date(raw, range_position=range_position)
    if parsed_text_date is not None:
        return parsed_text_date
    for candidate in (raw, raw.replace("Z", "+00:00")):
        try:
            return date.fromisoformat(candidate[:10])
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            continue
    return None


def _parse_jira_text_date(raw: str, *, range_position: str) -> date | None:
    for date_format in ("%b %d, %Y", "%B %d, %Y", "%b %d %Y", "%B %d %Y", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(raw, date_format).date()
        except ValueError:
            continue

    normalized = raw.replace("\u2013", "-").replace("\u2014", "-")
    iso_month_matches = list(re.finditer(r"\b(20\d{2})-(0?[1-9]|1[0-2])(?:-(0?[1-9]|[12]\d|3[01]))?\b", normalized))
    if iso_month_matches:
        selected = iso_month_matches[-1] if range_position == "end" else iso_month_matches[0]
        year = int(selected.group(1))
        month_number = int(selected.group(2))
        day = int(selected.group(3)) if selected.group(3) else (_last_day_of_month(year, month_number) if range_position == "end" else 1)
        return date(year, month_number, day)

    years = [int(match.group(0)) for match in re.finditer(r"\b20\d{2}\b", normalized)]
    month_matches = list(re.finditer(MONTH_NAME_PATTERN, normalized, flags=re.IGNORECASE))
    if not years or not month_matches:
        return None

    selected_month_match = month_matches[-1] if range_position == "end" else month_matches[0]
    month_number = MONTH_NAME_LOOKUP[selected_month_match.group(0).casefold()]
    year = years[-1] if range_position == "end" else years[0]
    if len(years) == 1 and len(month_matches) > 1:
        first_month = MONTH_NAME_LOOKUP[month_matches[0].group(0).casefold()]
        last_month = MONTH_NAME_LOOKUP[month_matches[-1].group(0).casefold()]
        if range_position == "end" and first_month > last_month:
            year += 1
    day = _last_day_of_month(year, month_number) if range_position == "end" else 1
    return date(year, month_number, day)


def _last_day_of_month(year: int, month: int) -> int:
    if month == 12:
        return 31
    return (date(year, month + 1, 1) - date(year, month, 1)).days


def _normalize_jira_field_key(key: str) -> str:
    return "".join(character for character in key.casefold() if character.isalnum())


def _bucket_id_from_category(db: Session, category: str | None) -> int | None:
    if not category:
        return None
    bucket_code = ROADMAP_CATEGORY_ALIASES.get(normalize_lookup_value(category))
    if bucket_code is None:
        return None
    bucket = db.scalar(select(Bucket).where(Bucket.code == bucket_code))
    return bucket.id if bucket else None


def _labels_from_issue(issue: dict[str, object]) -> tuple[str, ...]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    labels = fields.get("labels") if isinstance(fields, dict) else []
    if not isinstance(labels, list):
        return tuple()
    return tuple(str(label).strip() for label in labels if str(label).strip())


def _has_fiscal_year_label(labels: tuple[str, ...], fiscal_year: int) -> bool:
    expected = _roadmap_fiscal_year_label(fiscal_year)
    return any(label.strip().casefold() == expected.casefold() for label in labels)


def _roadmap_fiscal_year_label(fiscal_year: int) -> str:
    return f"FY{fiscal_year % 100:02d}"


def _roadmap_payload_hash(payload: RoadmapIssuePayload) -> str:
    raw = "|".join(
        [
            payload.issue_id,
            payload.issue_key,
            payload.title,
            payload.status or "",
            ",".join(sorted(payload.labels)),
            payload.program_area or "",
            payload.category or "",
            payload.source_team or "",
            payload.roadmap_start_date.isoformat() if payload.roadmap_start_date else "",
            payload.roadmap_end_date.isoformat() if payload.roadmap_end_date else "",
            ",".join(str(month_sequence) for month_sequence in payload.roadmap_schedule_months),
            ",".join(
                sorted(
                    "|".join(
                        [
                            link.issue_key,
                            link.jira_project_key or "",
                            link.issue_type or "",
                            link.status or "",
                            link.category or "",
                        ]
                    )
                    for link in payload.links
                )
            ),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_issue_key(value: str | None) -> str:
    return (value or "").strip().upper()


def _project_key_from_issue_key(issue_key: str) -> str | None:
    if "-" not in issue_key:
        return None
    return issue_key.split("-", 1)[0].strip().upper() or None


def _roadmap_actual_sort_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    status_order = {"mapped": "0", "ambiguous": "1", "unmapped": "2"}
    return (
        status_order.get(str(row["mapping_status"]), "9"),
        str(row["roadmap_item_key"] or ""),
        str(row["team_member"]),
        str(row["bucket"]),
    )
