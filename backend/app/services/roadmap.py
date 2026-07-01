from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
import hashlib

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import ActualEntry, Bucket, FiscalMonth, Product, ProductJiraSpace, RoadmapItem, RoadmapItemIssueLink, SyncRun
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
    source_url: str | None
    links: tuple[RoadmapIssueLinkPayload, ...]


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
        "source_url": item.source_url,
        "linked_issue_count": len(scoped_links),
        "linked_issues": [_serialize_roadmap_issue_link(link) for link in scoped_links],
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
    deliverable_parent_items = [
        item
        for item in deliverable_parent_items
        if any(link.product_id == product_id and _is_roadmap_deliverable_issue_type(link.issue_type) for link in item.issue_links)
    ]
    items_by_id = {item.id: item for item in [*direct_items, *deliverable_parent_items]}
    items = sorted(items_by_id.values(), key=lambda item: item.jira_issue_key)
    return [serialize_roadmap_item(item, product_id=product_id) for item in items if _is_roadmap_item_issue_type(item.issue_type)]


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
        fields = ["summary", "status", "issuetype", "labels", "issuelinks", *field_ids["agency_office"], *field_ids["category"]]
        issues = _search_jira_issues(client, site_url, jql, fields)
        payloads: list[RoadmapIssuePayload] = []
        for issue in issues:
            labels = _labels_from_issue(issue)
            if _is_roadmap_item_issue_type(_issue_type_name(issue)) and _has_fiscal_year_label(labels, fiscal_year):
                payloads.append(_normalize_roadmap_issue(site_url, issue, field_ids["agency_office"], field_ids["category"]))
        return _enrich_roadmap_payload_links(client, site_url, payloads, field_ids["category"])


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
) -> RoadmapIssuePayload:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    status = fields.get("status") if isinstance(fields.get("status"), dict) else {}
    status_category = status.get("statusCategory") if isinstance(status.get("statusCategory"), dict) else {}
    issue_type = fields.get("issuetype") if isinstance(fields.get("issuetype"), dict) else {}
    issue_key = _normalize_issue_key(str(issue.get("key") or ""))
    links = tuple(_extract_issue_links(fields, issue_key, category_field_ids))
    labels = _labels_from_issue(issue)
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


def _fetch_roadmap_field_ids(client: httpx.Client, site_url: str) -> dict[str, list[str]]:
    response = client.get(f"{site_url.rstrip('/')}/rest/api/3/field", headers={"Accept": "application/json"})
    _raise_for_jira_response(response)
    fields = response.json()
    if not isinstance(fields, list):
        return {"agency_office": [], "category": []}
    return {
        "agency_office": _jira_field_ids_by_name(fields, AGENCY_OFFICE_FIELD_NAMES),
        "category": _jira_field_ids_by_name(fields, CATEGORY_FIELD_NAMES),
    }


def _jira_field_ids_by_name(fields: list[object], names: set[str]) -> list[str]:
    return [
        str(field["id"])
        for field in fields
        if isinstance(field, dict)
        and str(field.get("name") or "").strip().casefold() in names
        and field.get("id")
    ]


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
