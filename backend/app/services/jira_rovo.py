from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActualEntry, Bucket, FiscalMonth, JiraProductMapping, JiraUserMapping, Product, SyncRun, TeamMember
from app.models.entities import utcnow
from app.services.fiscal_year import ensure_fiscal_months, fiscal_sequence_for_date, fiscal_year_for_date


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
    bucket_code: str
    worked_on: date
    hours: Decimal


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
            bucket = db.scalar(select(Bucket).where(Bucket.code == worklog.bucket_code))
            user_mapping = _ensure_user_mapping(db, worklog)
            product_mapping = _ensure_product_mapping(db, worklog)

            if bucket is None or user_mapping.team_member_id is None or product_mapping.product_id is None:
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


def map_jira_product(db: Session, mapping_id: int, product_id: int | None) -> dict[str, object]:
    mapping = db.get(JiraProductMapping, mapping_id)
    if mapping is None:
        raise ValueError("Jira product mapping not found")
    if product_id is not None and db.get(Product, product_id) is None:
        raise ValueError("Product not found")
    mapping.product_id = product_id
    db.flush()
    return {
        "id": mapping.id,
        "jira_project_key": mapping.jira_project_key,
        "jira_project_name": mapping.jira_project_name,
        "product_id": mapping.product_id,
        "product": mapping.product.name if mapping.product else None,
    }


def list_sync_runs(db: Session, limit: int = 20) -> list[dict[str, object]]:
    runs = db.scalars(select(SyncRun).order_by(SyncRun.started_at.desc()).limit(limit)).all()
    return [serialize_sync_run(run) for run in runs]


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
    if mapping is None:
        mapping = JiraProductMapping(
            jira_project_key=worklog.jira_project_key,
            jira_project_name=worklog.jira_project_name,
        )
        db.add(mapping)
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
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
