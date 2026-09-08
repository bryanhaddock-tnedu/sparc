from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import hashlib

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ActualEntry,
    Bucket,
    FiscalMonth,
    JiraProductMapping,
    JiraUserMapping,
    JiraWorklogExclusion,
    Product,
    ProductJiraSpace,
    SyncRun,
    TeamMember,
)
from app.models.entities import utcnow
from app.services.estimation_policy import WORK_TYPE_ALIASES, normalize_lookup_value
from app.services.fiscal_year import current_fiscal_year, ensure_fiscal_months, fiscal_sequence_for_date, fiscal_year_for_date
from app.services.jira_projects import _raise_for_jira_response

WORK_TYPE_FIELD_NAMES = {
    "Work Type",
    "Type of Work",
    "Work Category",
    "Development Type",
    "Request Type",
}
TEAM_FIELD_NAMES = {"team"}
STORY_POINT_FIELD_NAMES = {"story points", "story point estimate"}


@dataclass(frozen=True)
class MockWorklog:
    worklog_id: str
    issue_id: str
    ticket_key: str
    ticket_summary: str
    ticket_status: str
    jira_project_key: str
    jira_project_name: str
    jira_account_id: str
    jira_display_name: str
    jira_email: str | None
    bucket_code: str | None
    worked_on: date
    hours: Decimal
    source_issue_type: str | None = None
    parent_ticket_key: str | None = None
    parent_ticket_summary: str | None = None
    work_type_value: str | None = None
    source_team: str | None = None
    story_points: Decimal | None = None


MOCK_WORKLOGS = [
    MockWorklog("wl-1001", "100241", "SIS-241", "New enrollment intake", "Done", "SIS", "Student Information", "acct-avery", "Avery Johnson", "avery@example.test", "NET_NEW", date(2025, 7, 14), Decimal("18")),
    MockWorklog("wl-1002", "100245", "SIS-245", "Transcript usability fixes", "Done", "SIS", "Student Information", "acct-morgan", "Morgan Lee", "morgan@example.test", "ENHANCE", date(2025, 8, 5), Decimal("22")),
    MockWorklog("wl-1003", "200782", "EDL-782", "License renewal support", "Done", "EDL", "Educator Licensing", "acct-sam", "Sam Patel", "sam@example.test", "MAINTENANCE", date(2025, 9, 21), Decimal("16")),
    MockWorklog("wl-1004", "300419", "DWH-419", "Longitudinal model buildout", "Done", "DWH", "Data Warehouse", "acct-riley", "Riley Chen", "riley@example.test", "NET_NEW", date(2025, 10, 9), Decimal("26")),
    MockWorklog("wl-1005", "300433", "DWH-433", "Quality rule enhancements", "Done", "DWH", "Data Warehouse", "acct-jordan", "Jordan Smith", "jordan@example.test", "ENHANCE", date(2026, 1, 12), Decimal("31")),
    MockWorklog("wl-1006", "100266", "SIS-266", "Operational patching", "Done", "SIS", "Student Information", "acct-avery", "Avery Johnson", "avery@example.test", "MAINTENANCE", date(2026, 3, 17), Decimal("12")),
    MockWorklog("wl-1007", "400018", "GRN-18", "Grant intake discovery", "Done", "GRN", "Grants Portal", "acct-unmapped-user", "Taylor Unmapped", "taylor@example.test", "NET_NEW", date(2026, 4, 4), Decimal("8")),
]


def run_mock_jira_rovo_sync(db: Session) -> dict[str, object]:
    sync_run = SyncRun(source="mock_jira_rovo", mode="mock", status="running")
    db.add(sync_run)
    db.flush()
    imported = 0
    skipped_unmapped = 0

    try:
        for worklog in MOCK_WORKLOGS:
            fiscal_year = fiscal_year_for_date(worklog.worked_on)
            fiscal_month = _ensure_month_for_worklog(db, fiscal_year, worklog.worked_on)
            bucket = _bucket_for_worklog(db, worklog)
            user_mapping = _ensure_user_mapping(db, worklog)
            product_mapping = _ensure_product_mapping(db, worklog)

            if bucket is None or user_mapping.team_member_id is None or product_mapping.product_id is None:
                _record_worklog_exclusion(db, sync_run, worklog, bucket, user_mapping, product_mapping)
                skipped_unmapped += 1
                continue

            existing = db.scalar(
                select(ActualEntry).where(
                    ActualEntry.source_issue_id == worklog.issue_id,
                    ActualEntry.source_worklog_id == worklog.worklog_id,
                )
            )
            if existing is None:
                existing = db.scalar(
                    select(ActualEntry).where(
                        ActualEntry.source_ticket_key == worklog.ticket_key,
                        ActualEntry.source_worklog_id == worklog.worklog_id,
                    )
                )
            payload_hash = _payload_hash(worklog)
            if existing is None:
                db.add(
                    ActualEntry(
                        sync_run_id=sync_run.id,
                        product_id=product_mapping.product_id,
                        team_member_id=user_mapping.team_member_id,
                        bucket_id=bucket.id,
                        fiscal_month_id=fiscal_month.id,
                        hours=worklog.hours,
                        source="mock_jira_rovo",
                        source_issue_id=worklog.issue_id,
                        source_ticket_key=worklog.ticket_key,
                        source_worklog_id=worklog.worklog_id,
                        source_account_id=worklog.jira_account_id,
                        source_project_key=worklog.jira_project_key,
                        source_ticket_summary=worklog.ticket_summary,
                        source_issue_type=worklog.source_issue_type,
                        source_parent_ticket_key=worklog.parent_ticket_key,
                        source_parent_ticket_summary=worklog.parent_ticket_summary,
                        source_team=worklog.source_team,
                        source_story_points=worklog.story_points,
                        source_payload_hash=payload_hash,
                        is_team_member_time=True,
                        worked_on=worklog.worked_on,
                    )
                )
            else:
                existing.sync_run_id = sync_run.id
                existing.product_id = product_mapping.product_id
                existing.team_member_id = user_mapping.team_member_id
                existing.bucket_id = bucket.id
                existing.fiscal_month_id = fiscal_month.id
                existing.hours = worklog.hours
                existing.source_ticket_key = worklog.ticket_key
                existing.source_account_id = worklog.jira_account_id
                existing.source_project_key = worklog.jira_project_key
                existing.source_ticket_summary = worklog.ticket_summary
                existing.source_issue_type = worklog.source_issue_type
                existing.source_parent_ticket_key = worklog.parent_ticket_key
                existing.source_parent_ticket_summary = worklog.parent_ticket_summary
                existing.source_team = worklog.source_team
                existing.source_story_points = worklog.story_points
                existing.source_payload_hash = payload_hash
                existing.is_team_member_time = True
                existing.worked_on = worklog.worked_on
            imported += 1

        sync_run.status = "completed"
        sync_run.imported_count = imported
        sync_run.skipped_count = skipped_unmapped
        sync_run.completed_at = utcnow()
    except Exception as exc:
        sync_run.status = "failed"
        sync_run.imported_count = imported
        sync_run.skipped_count = skipped_unmapped
        sync_run.completed_at = utcnow()
        sync_run.error_summary = str(exc)
        raise

    db.flush()
    return {
        "source": "mock_jira_rovo",
        "sync_run": serialize_sync_run(sync_run),
        "imported_worklogs": imported,
        "skipped_unmapped_worklogs": skipped_unmapped,
        "unmapped_users": list_unmapped_users(db),
        "unmapped_products": list_unmapped_products(db),
    }


def jira_integration_status() -> dict[str, object]:
    settings = get_settings()
    missing = []
    if not settings.jira_site_url:
        missing.append("JIRA_SITE_URL")
    if not settings.jira_api_email:
        missing.append("JIRA_API_EMAIL")
    if not settings.jira_api_token:
        missing.append("JIRA_API_TOKEN")
    return {
        "configured": not missing,
        "site_url": _masked_site_url(settings.jira_site_url),
        "auth_email_configured": bool(settings.jira_api_email),
        "api_token_configured": bool(settings.jira_api_token),
        "missing": missing,
    }


def current_live_sync_fiscal_year() -> int:
    return current_fiscal_year()


def run_live_jira_rovo_sync(db: Session, requested_fiscal_year: int | None = None) -> dict[str, object]:
    fiscal_year = current_live_sync_fiscal_year()
    sync_run = SyncRun(source="jira", mode="live", status="running")
    db.add(sync_run)
    db.flush()
    imported = 0
    skipped_unmapped = 0
    deleted = 0

    try:
        worklogs = fetch_live_jira_worklogs(db, fiscal_year)
        current_worklog_ids = {_worklog_id(worklog) for worklog in worklogs if _worklog_id(worklog)}
        for worklog in worklogs:
            fiscal_month = _ensure_month_for_worklog(db, fiscal_year_for_date(worklog.worked_on), worklog.worked_on)
            bucket = _bucket_for_worklog(db, worklog)
            user_mapping = _ensure_user_mapping(db, worklog)
            product_mapping = _ensure_product_mapping(db, worklog)
            existing = _existing_live_actual(db, worklog)

            if bucket is None or user_mapping.team_member_id is None or product_mapping.product_id is None:
                _record_worklog_exclusion(db, sync_run, worklog, bucket, user_mapping, product_mapping)
                if existing is not None:
                    db.delete(existing)
                    deleted += 1
                skipped_unmapped += 1
                continue

            payload_hash = _payload_hash(worklog)
            if existing is None:
                db.add(
                    ActualEntry(
                        sync_run_id=sync_run.id,
                        product_id=product_mapping.product_id,
                        team_member_id=user_mapping.team_member_id,
                        bucket_id=bucket.id,
                        fiscal_month_id=fiscal_month.id,
                        hours=worklog.hours,
                        source="jira",
                        source_issue_id=worklog.issue_id,
                        source_ticket_key=worklog.ticket_key,
                        source_worklog_id=worklog.worklog_id,
                        source_account_id=worklog.jira_account_id,
                        source_project_key=worklog.jira_project_key,
                        source_ticket_summary=worklog.ticket_summary,
                        source_issue_type=worklog.source_issue_type,
                        source_parent_ticket_key=worklog.parent_ticket_key,
                        source_parent_ticket_summary=worklog.parent_ticket_summary,
                        source_team=worklog.source_team,
                        source_story_points=worklog.story_points,
                        source_payload_hash=payload_hash,
                        is_team_member_time=True,
                        worked_on=worklog.worked_on,
                    )
                )
            else:
                existing.sync_run_id = sync_run.id
                existing.product_id = product_mapping.product_id
                existing.team_member_id = user_mapping.team_member_id
                existing.bucket_id = bucket.id
                existing.fiscal_month_id = fiscal_month.id
                existing.hours = worklog.hours
                existing.source_ticket_key = worklog.ticket_key
                existing.source_account_id = worklog.jira_account_id
                existing.source_project_key = worklog.jira_project_key
                existing.source_ticket_summary = worklog.ticket_summary
                existing.source_issue_type = worklog.source_issue_type
                existing.source_parent_ticket_key = worklog.parent_ticket_key
                existing.source_parent_ticket_summary = worklog.parent_ticket_summary
                existing.source_team = worklog.source_team
                existing.source_story_points = worklog.story_points
                existing.source_payload_hash = payload_hash
                existing.is_team_member_time = True
                existing.worked_on = worklog.worked_on
            imported += 1

        deleted += _delete_stale_live_actuals(db, fiscal_year, current_worklog_ids, _active_jira_project_keys(db))
        sync_run.status = "completed"
        sync_run.imported_count = imported
        sync_run.skipped_count = skipped_unmapped
        sync_run.completed_at = utcnow()
    except Exception as exc:
        sync_run.status = "failed"
        sync_run.imported_count = imported
        sync_run.skipped_count = skipped_unmapped
        sync_run.completed_at = utcnow()
        sync_run.error_summary = str(exc)
        raise

    db.flush()
    return {
        "source": "jira",
        "fiscal_year": fiscal_year,
        "requested_fiscal_year": requested_fiscal_year,
        "uses_current_fiscal_year": True,
        "sync_run": serialize_sync_run(sync_run),
        "imported_worklogs": imported,
        "skipped_unmapped_worklogs": skipped_unmapped,
        "deleted_worklogs": deleted,
        "unmapped_users": list_unmapped_users(db),
        "unmapped_products": list_unmapped_products(db),
    }


def fetch_live_jira_worklogs(db: Session, fiscal_year: int) -> list[MockWorklog]:
    settings = get_settings()
    _require_jira_settings(settings.jira_site_url, settings.jira_api_email, settings.jira_api_token)
    spaces = db.scalars(
        select(ProductJiraSpace)
        .join(ProductJiraSpace.product)
        .where(ProductJiraSpace.is_active.is_(True), Product.is_active.is_(True))
        .order_by(ProductJiraSpace.jira_project_key)
    ).all()
    if not spaces:
        raise ValueError("No active Product/Jira space mappings are configured")

    fiscal_start = date(fiscal_year - 1, 7, 1)
    fiscal_end = date(fiscal_year, 6, 30)
    jql = _worklog_jql(spaces, fiscal_start, fiscal_end)
    worklogs: list[MockWorklog] = []
    with httpx.Client(timeout=45, auth=(settings.jira_api_email, settings.jira_api_token)) as client:
        work_type_field_ids = _fetch_work_type_field_ids(client, settings.jira_site_url)
        team_field_ids = _fetch_field_ids(client, settings.jira_site_url, TEAM_FIELD_NAMES)
        story_point_field_ids = _fetch_field_ids(client, settings.jira_site_url, STORY_POINT_FIELD_NAMES)
        field_ids = [*work_type_field_ids, *team_field_ids, *story_point_field_ids]
        fields = ["project", "summary", "status", "issuetype", "parent", "worklog", *field_ids]
        for issue in _search_jira_issues(client, settings.jira_site_url, jql, fields):
            issue_worklogs = _issue_worklogs(client, settings.jira_site_url, issue)
            for worklog in issue_worklogs:
                normalized = _normalize_jira_worklog(issue, worklog, work_type_field_ids, fiscal_start, fiscal_end, team_field_ids, story_point_field_ids)
                if normalized is not None:
                    worklogs.append(normalized)
    return worklogs


def _existing_live_actual(db: Session, worklog: MockWorklog) -> ActualEntry | None:
    return db.scalar(
        select(ActualEntry).where(
            ActualEntry.source == "jira",
            ActualEntry.source_issue_id == worklog.issue_id,
            ActualEntry.source_worklog_id == worklog.worklog_id,
        )
    )


def _delete_stale_live_actuals(
    db: Session,
    fiscal_year: int,
    current_worklog_ids: set[str],
    active_project_keys: set[str],
) -> int:
    entries = db.scalars(
        select(ActualEntry)
        .join(ActualEntry.fiscal_month)
        .where(
            ActualEntry.source == "jira",
            FiscalMonth.fiscal_year == fiscal_year,
            ActualEntry.source_project_key.in_(active_project_keys),
        )
    ).all()
    deleted = 0
    for entry in entries:
        if _actual_entry_worklog_id(entry) in current_worklog_ids:
            continue
        db.delete(entry)
        deleted += 1
    return deleted


def _active_jira_project_keys(db: Session) -> set[str]:
    return set(
        db.scalars(
            select(ProductJiraSpace.jira_project_key)
            .join(ProductJiraSpace.product)
            .where(ProductJiraSpace.is_active.is_(True), Product.is_active.is_(True))
        ).all()
    )


def _worklog_id(worklog: MockWorklog) -> str:
    return str(worklog.worklog_id or "").strip()


def _actual_entry_worklog_id(entry: ActualEntry) -> str:
    return str(entry.source_worklog_id or "").strip()


def list_unmapped_users(db: Session) -> list[dict[str, object]]:
    mappings = db.scalars(
        select(JiraUserMapping).where(JiraUserMapping.team_member_id.is_(None)).order_by(JiraUserMapping.jira_display_name)
    ).all()
    return [
        {
            "id": mapping.id,
            "jira_account_id": mapping.jira_account_id,
            "jira_display_name": mapping.jira_display_name,
            "jira_email": mapping.jira_email,
            "team_member_id": mapping.team_member_id,
            "team_member": mapping.team_member.name if mapping.team_member else None,
        }
        for mapping in mappings
    ]


def list_unmapped_products(db: Session) -> list[dict[str, object]]:
    mappings = db.scalars(
        select(JiraProductMapping)
        .where(JiraProductMapping.product_id.is_(None))
        .order_by(JiraProductMapping.jira_project_name)
    ).all()
    return [
        {
            "id": mapping.id,
            "jira_project_key": mapping.jira_project_key,
            "jira_project_name": mapping.jira_project_name,
            "product_id": mapping.product_id,
            "product": mapping.product.name if mapping.product else None,
        }
        for mapping in mappings
    ]


def list_user_mappings(db: Session) -> list[dict[str, object]]:
    mappings = db.scalars(select(JiraUserMapping).order_by(JiraUserMapping.jira_display_name)).all()
    return [
        {
            "id": mapping.id,
            "jira_account_id": mapping.jira_account_id,
            "jira_display_name": mapping.jira_display_name,
            "jira_email": mapping.jira_email,
            "team_member_id": mapping.team_member_id,
            "team_member": mapping.team_member.name if mapping.team_member else None,
        }
        for mapping in mappings
    ]


def list_product_mappings(db: Session) -> list[dict[str, object]]:
    mappings = db.scalars(select(JiraProductMapping).order_by(JiraProductMapping.jira_project_name)).all()
    return [
        {
            "id": mapping.id,
            "jira_project_key": mapping.jira_project_key,
            "jira_project_name": mapping.jira_project_name,
            "product_id": mapping.product_id,
            "product": mapping.product.name if mapping.product else None,
        }
        for mapping in mappings
    ]


def map_jira_user(db: Session, mapping_id: int, team_member_id: int | None) -> dict[str, object]:
    mapping = db.get(JiraUserMapping, mapping_id)
    if mapping is None:
        raise ValueError("Jira user mapping not found")
    if team_member_id is not None and db.get(TeamMember, team_member_id) is None:
        raise ValueError("Team member not found")
    mapping.team_member_id = team_member_id
    db.flush()
    return {
        "id": mapping.id,
        "jira_account_id": mapping.jira_account_id,
        "jira_display_name": mapping.jira_display_name,
        "jira_email": mapping.jira_email,
        "team_member_id": mapping.team_member_id,
        "team_member": mapping.team_member.name if mapping.team_member else None,
    }


def list_sync_runs(db: Session, limit: int = 20) -> list[dict[str, object]]:
    runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)).all()
    return [serialize_sync_run(run) for run in runs]


def list_latest_worklog_exclusions(db: Session) -> dict[str, object]:
    sync_run = db.scalar(
        select(SyncRun)
        .where(
            SyncRun.source == "jira",
            SyncRun.status == "completed",
        )
        .order_by(SyncRun.started_at.desc())
        .limit(1)
    )
    if sync_run is None:
        return {
            "sync_run_id": None,
            "completed_at": None,
            "excluded_worklog_count": 0,
            "details_available": True,
            "tickets": [],
        }

    exclusions = db.scalars(
        select(JiraWorklogExclusion)
        .where(JiraWorklogExclusion.sync_run_id == sync_run.id)
        .order_by(JiraWorklogExclusion.ticket_key, JiraWorklogExclusion.worked_on, JiraWorklogExclusion.id)
    ).all()
    grouped: dict[str, dict[str, object]] = {}
    for exclusion in exclusions:
        group = grouped.setdefault(
            exclusion.ticket_key,
            {
                "ticket_key": exclusion.ticket_key,
                "ticket_summary": exclusion.ticket_summary,
                "jira_project_key": exclusion.jira_project_key,
                "jira_project_name": exclusion.jira_project_name,
                "worklog_count": 0,
                "hours": Decimal("0"),
                "worked_on_start": exclusion.worked_on,
                "worked_on_end": exclusion.worked_on,
                "jira_users": set(),
                "work_type_values": set(),
                "reason_codes": set(),
            },
        )
        group["worklog_count"] += 1
        group["hours"] += exclusion.hours
        group["worked_on_start"] = min(group["worked_on_start"], exclusion.worked_on)
        group["worked_on_end"] = max(group["worked_on_end"], exclusion.worked_on)
        if exclusion.jira_display_name:
            group["jira_users"].add(exclusion.jira_display_name)
        if exclusion.work_type_value:
            group["work_type_values"].add(exclusion.work_type_value)
        if exclusion.invalid_work_type:
            group["reason_codes"].add("unrecognized_work_type" if exclusion.work_type_value else "missing_work_type")
        if exclusion.unmapped_user:
            group["reason_codes"].add("unmapped_user")
        if exclusion.unmapped_product:
            group["reason_codes"].add("unmapped_product")

    site_url = (get_settings().jira_site_url or "").rstrip("/")
    tickets = []
    for group in grouped.values():
        tickets.append(
            {
                **group,
                "jira_url": f"{site_url}/browse/{group['ticket_key']}" if site_url else None,
                "jira_users": sorted(group["jira_users"]),
                "work_type_values": sorted(group["work_type_values"]),
                "reason_codes": sorted(group["reason_codes"]),
            }
        )
    return {
        "sync_run_id": sync_run.id,
        "completed_at": sync_run.completed_at,
        "excluded_worklog_count": sync_run.skipped_count,
        "details_available": sync_run.skipped_count == 0 or bool(exclusions),
        "tickets": tickets,
    }


def serialize_sync_run(run: SyncRun) -> dict[str, object]:
    return {
        "id": run.id,
        "source": run.source,
        "mode": run.mode,
        "status": run.status,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "imported_count": run.imported_count,
        "skipped_count": run.skipped_count,
        "error_summary": run.error_summary,
    }


def _record_worklog_exclusion(
    db: Session,
    sync_run: SyncRun,
    worklog: MockWorklog,
    bucket: Bucket | None,
    user_mapping: JiraUserMapping,
    product_mapping: JiraProductMapping,
) -> None:
    db.add(
        JiraWorklogExclusion(
            sync_run_id=sync_run.id,
            source_issue_id=worklog.issue_id,
            source_worklog_id=worklog.worklog_id,
            ticket_key=worklog.ticket_key,
            ticket_summary=worklog.ticket_summary,
            jira_project_key=worklog.jira_project_key,
            jira_project_name=worklog.jira_project_name,
            jira_account_id=worklog.jira_account_id or None,
            jira_display_name=worklog.jira_display_name or None,
            worked_on=worklog.worked_on,
            hours=worklog.hours,
            work_type_value=worklog.work_type_value,
            invalid_work_type=bucket is None,
            unmapped_user=user_mapping.team_member_id is None,
            unmapped_product=product_mapping.product_id is None,
        )
    )


def _ensure_month_for_worklog(db: Session, fiscal_year: int, worked_on: date) -> FiscalMonth:
    ensure_fiscal_months(db, fiscal_year)
    month = db.scalar(
        select(FiscalMonth).where(
            FiscalMonth.fiscal_year == fiscal_year,
            FiscalMonth.sequence == fiscal_sequence_for_date(worked_on),
        )
    )
    if month is None:
        raise ValueError("Unable to normalize worklog into a fiscal month")
    return month


def _ensure_user_mapping(db: Session, worklog: MockWorklog) -> JiraUserMapping:
    mapping = db.scalar(select(JiraUserMapping).where(JiraUserMapping.jira_account_id == worklog.jira_account_id))
    if mapping is None:
        mapping = JiraUserMapping(
            jira_account_id=worklog.jira_account_id,
            jira_display_name=worklog.jira_display_name,
            jira_email=worklog.jira_email,
        )
        db.add(mapping)
        db.flush()
    return mapping


def _ensure_product_mapping(db: Session, worklog: MockWorklog) -> JiraProductMapping:
    mapping = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == worklog.jira_project_key))
    product_space = db.scalar(
        select(ProductJiraSpace).where(
            ProductJiraSpace.jira_project_key == worklog.jira_project_key,
            ProductJiraSpace.is_active.is_(True),
            ProductJiraSpace.product.has(Product.is_active.is_(True)),
        )
    )
    if mapping is None:
        mapping = JiraProductMapping(
            jira_project_key=worklog.jira_project_key,
            jira_project_name=worklog.jira_project_name,
            product_id=product_space.product_id if product_space is not None else None,
        )
        db.add(mapping)
        db.flush()
    else:
        mapping.jira_project_name = worklog.jira_project_name
        mapping.product_id = product_space.product_id if product_space is not None else None
        db.flush()
    return mapping


def _payload_hash(worklog: MockWorklog) -> str:
    raw = "|".join(
        [
            worklog.issue_id,
            worklog.ticket_key,
            worklog.worklog_id,
            worklog.jira_account_id,
            worklog.worked_on.isoformat(),
            str(worklog.hours),
            worklog.source_issue_type or "",
            worklog.parent_ticket_key or "",
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _require_jira_settings(site_url: str | None, email: str | None, token: str | None) -> None:
    if not site_url or not email or not token:
        raise ValueError("Jira credentials are not configured")


def _masked_site_url(site_url: str | None) -> str | None:
    if not site_url:
        return None
    return site_url.rstrip("/")


def _worklog_jql(spaces: list[ProductJiraSpace], fiscal_start: date, fiscal_end: date) -> str:
    clauses = []
    for space in spaces:
        if space.scope_jql and space.scope_jql.strip():
            clauses.append(f"({space.scope_jql.strip()})")
        else:
            clauses.append(f'project = "{space.jira_project_key}"')
    project_scope = " OR ".join(clauses)
    return f"({project_scope}) AND worklogDate >= {fiscal_start.isoformat()} AND worklogDate <= {fiscal_end.isoformat()} ORDER BY updated ASC"


def _fetch_work_type_field_ids(client: httpx.Client, site_url: str) -> list[str]:
    return _fetch_field_ids(client, site_url, {name.casefold() for name in WORK_TYPE_FIELD_NAMES})


def _fetch_field_ids(client: httpx.Client, site_url: str, names: set[str]) -> list[str]:
    response = client.get(f"{site_url.rstrip('/')}/rest/api/3/field", headers={"Accept": "application/json"})
    _raise_for_jira_response(response)
    fields = response.json()
    if not isinstance(fields, list):
        return []
    return [
        str(field["id"])
        for field in fields
        if isinstance(field, dict) and str(field.get("name") or "").strip().casefold() in names and field.get("id")
    ]


def _search_jira_issues(client: httpx.Client, site_url: str, jql: str, fields: list[str], expand: list[str] | None = None) -> list[dict[str, object]]:
    try:
        return _search_jira_issues_enhanced(client, site_url, jql, fields, expand=expand)
    except ValueError as exc:
        if "404" not in str(exc):
            raise
    return _search_jira_issues_legacy(client, site_url, jql, fields, expand=expand)


def _search_jira_issues_enhanced(client: httpx.Client, site_url: str, jql: str, fields: list[str], expand: list[str] | None = None) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    next_page_token: str | None = None
    while True:
        payload: dict[str, object] = {
            "jql": jql,
            "maxResults": 50,
            "fields": fields,
        }
        if expand:
            payload["expand"] = ",".join(expand)
        if next_page_token:
            payload["nextPageToken"] = next_page_token
        response = client.post(
            f"{site_url.rstrip('/')}/rest/api/3/search/jql",
            json=payload,
            headers={"Accept": "application/json"},
        )
        if response.status_code == 404:
            raise ValueError("Jira enhanced search endpoint returned 404")
        _raise_for_jira_response(response)
        data = response.json()
        issues.extend(data.get("issues", []))
        next_page_token = data.get("nextPageToken")
        if not next_page_token or data.get("isLast", False):
            break
    return issues


def _search_jira_issues_legacy(client: httpx.Client, site_url: str, jql: str, fields: list[str], expand: list[str] | None = None) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    start_at = 0
    while True:
        payload: dict[str, object] = {"jql": jql, "startAt": start_at, "maxResults": 50, "fields": fields}
        if expand:
            payload["expand"] = ",".join(expand)
        response = client.post(
            f"{site_url.rstrip('/')}/rest/api/3/search",
            json=payload,
            headers={"Accept": "application/json"},
        )
        _raise_for_jira_response(response)
        data = response.json()
        values = data.get("issues", [])
        issues.extend(values)
        start_at += len(values)
        if len(values) == 0 or start_at >= data.get("total", 0):
            break
    return issues


def _issue_worklogs(client: httpx.Client, site_url: str, issue: dict[str, object]) -> list[dict[str, object]]:
    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    embedded = fields.get("worklog") if isinstance(fields, dict) and isinstance(fields.get("worklog"), dict) else {}
    worklogs = list(embedded.get("worklogs", [])) if isinstance(embedded, dict) else []
    total = int(embedded.get("total", len(worklogs)) or 0) if isinstance(embedded, dict) else len(worklogs)
    if len(worklogs) >= total:
        return worklogs

    all_worklogs: list[dict[str, object]] = []
    start_at = 0
    issue_key = str(issue.get("key") or issue.get("id") or "")
    while True:
        response = client.get(
            f"{site_url.rstrip('/')}/rest/api/3/issue/{issue_key}/worklog",
            params={"startAt": start_at, "maxResults": 100},
            headers={"Accept": "application/json"},
        )
        _raise_for_jira_response(response)
        data = response.json()
        values = data.get("worklogs", [])
        all_worklogs.extend(values)
        start_at += len(values)
        if len(values) == 0 or start_at >= data.get("total", 0):
            break
    return all_worklogs


def _normalize_jira_worklog(
    issue: dict[str, object],
    worklog: dict[str, object],
    work_type_field_ids: list[str],
    fiscal_start: date,
    fiscal_end: date,
    team_field_ids: list[str],
    story_point_field_ids: list[str],
) -> MockWorklog | None:
    worked_on = _jira_worklog_date(worklog.get("started"))
    if worked_on is None or worked_on < fiscal_start or worked_on > fiscal_end:
        return None

    fields = issue.get("fields") if isinstance(issue.get("fields"), dict) else {}
    project = fields.get("project") if isinstance(fields, dict) and isinstance(fields.get("project"), dict) else {}
    status = fields.get("status") if isinstance(fields, dict) and isinstance(fields.get("status"), dict) else {}
    issue_type = fields.get("issuetype") if isinstance(fields, dict) and isinstance(fields.get("issuetype"), dict) else {}
    parent_key, parent_summary = _parent_issue_details(fields)
    author = worklog.get("author") if isinstance(worklog.get("author"), dict) else {}
    seconds = Decimal(str(worklog.get("timeSpentSeconds") or 0))
    hours = (seconds / Decimal("3600")).quantize(Decimal("0.01"))
    if hours <= 0:
        return None
    worklog_id = str(worklog.get("id") or "").strip()
    if not worklog_id:
        return None

    project_key = str(project.get("key") or "").strip().upper()
    if not project_key:
        return None

    bucket_code, work_type_value = _work_type_details_from_issue_fields(fields, work_type_field_ids)
    return MockWorklog(
        worklog_id=worklog_id,
        issue_id=str(issue.get("id") or issue.get("key") or ""),
        ticket_key=str(issue.get("key") or ""),
        ticket_summary=str(fields.get("summary") or ""),
        ticket_status=str(status.get("name") or ""),
        jira_project_key=project_key,
        jira_project_name=str(project.get("name") or project_key),
        jira_account_id=str(author.get("accountId") or ""),
        jira_display_name=str(author.get("displayName") or "Unknown Jira user"),
        jira_email=str(author.get("emailAddress") or "") or None,
        bucket_code=bucket_code,
        worked_on=worked_on,
        hours=hours,
        source_issue_type=str(issue_type.get("name") or "") or None,
        parent_ticket_key=parent_key,
        parent_ticket_summary=parent_summary,
        work_type_value=work_type_value,
        source_team=_first_issue_field_text(fields, team_field_ids),
        story_points=_first_issue_decimal(fields, story_point_field_ids),
    )


def _parent_issue_details(fields: dict[str, object]) -> tuple[str | None, str | None]:
    parent = fields.get("parent") if isinstance(fields.get("parent"), dict) else {}
    key = str(parent.get("key") or "").strip()
    if not key:
        return None, None
    parent_fields = parent.get("fields") if isinstance(parent.get("fields"), dict) else {}
    summary = str(parent_fields.get("summary") or "").strip() if isinstance(parent_fields, dict) else ""
    return key, summary or None


def _bucket_for_worklog(db: Session, worklog: MockWorklog) -> Bucket | None:
    if not worklog.bucket_code:
        return None
    return db.scalar(select(Bucket).where(Bucket.code == worklog.bucket_code))


def _bucket_code_from_issue_fields(fields: dict[str, object], work_type_field_ids: list[str]) -> str | None:
    return _work_type_details_from_issue_fields(fields, work_type_field_ids)[0]


def _work_type_details_from_issue_fields(
    fields: dict[str, object],
    work_type_field_ids: list[str],
) -> tuple[str | None, str | None]:
    first_value: str | None = None
    for field_id in work_type_field_ids:
        value = _jira_field_text(fields.get(field_id))
        if not value:
            continue
        if first_value is None:
            first_value = value
        bucket_code = WORK_TYPE_ALIASES.get(normalize_lookup_value(value))
        if bucket_code:
            return bucket_code, value
    return None, first_value


def _jira_field_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return str(value.get("value") or value.get("name") or "").strip()
    if isinstance(value, list):
        return " ".join(_jira_field_text(item) for item in value)
    return str(value).strip()


def _first_issue_field_text(fields: dict[str, object], field_ids: list[str]) -> str | None:
    for field_id in field_ids:
        value = _jira_field_text(fields.get(field_id))
        if value:
            return value
    return None


def _first_issue_decimal(fields: dict[str, object], field_ids: list[str]) -> Decimal | None:
    for field_id in field_ids:
        try:
            value = Decimal(str(fields.get(field_id) or ""))
        except Exception:
            continue
        if value >= 0:
            return value
    return None


def _jira_worklog_date(value: object) -> date | None:
    if not value:
        return None
    raw = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None
