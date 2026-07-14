from io import BytesIO
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.seed import _seed_buckets
from app.models import ActualEntry, Base, Bucket, JiraProductMapping, JiraUserMapping, Product, ProductJiraSpace, SyncRun, TeamMember
from app.services.fiscal_year import get_fiscal_month
from app.services.jira_rovo import (
    MockWorklog,
    _bucket_code_from_issue_fields,
    map_jira_user,
    run_live_jira_rovo_sync,
    run_mock_jira_rovo_sync,
)
from app.services.team_import import import_team_members


def session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return Session(engine)


def test_team_import_is_idempotent_for_csv():
    with session() as db:
        csv_content = (
            "First Name,Last Name,Role,Team,Bill Rate,Employment Type,Contracting Company\n"
            "Casey,Rivera,Developer,Applications,120,Employee,\n"
        ).encode()

        first = import_team_members(db, filename="team.csv", content=csv_content)
        second = import_team_members(db, filename="team.csv", content=csv_content)

        assert first["created"] == 1
        assert second["updated"] == 1
        assert db.scalar(select(TeamMember).where(TeamMember.name == "Casey Rivera")).bill_rate == Decimal("120")


def test_team_import_accepts_real_roster_xlsx_shape():
    with session() as db:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append([None, None, None, None, None, None, None])
        sheet.append(["Role", "Employment Type", "Company", "First Name", "Last Name", "Bill Rate", "Team"])
        sheet.append(["Sr. Dev", "Contractor", "Covendis", "Steven ", "McKee", "148.13", "Data Reporting"])
        sheet.append(["Dev", "Contractor", "Covendis", "Pooja ", None, "98.75", "Data Reporting"])
        sheet.append(["Sr. Dev", "FTE", "TDOE", "Tony ", None, None, "Data Reporting"])
        content = BytesIO()
        workbook.save(content)

        result = import_team_members(db, filename="team.xlsx", content=content.getvalue())

        assert result["created"] == 3
        assert result["failed"] == 0
        assert result["rows"][0]["row"] == 3
        assert db.scalar(select(TeamMember).where(TeamMember.name == "Steven McKee")).bill_rate == Decimal("148.13")
        assert db.scalar(select(TeamMember).where(TeamMember.name == "Pooja")).bill_rate == Decimal("98.75")
        tony = db.scalar(select(TeamMember).where(TeamMember.name == "Tony"))
        assert tony.bill_rate == Decimal("0")
        assert tony.contracting_company == "TDOE"


def test_team_import_requires_contractor_bill_rate():
    with session() as db:
        csv_content = (
            "First Name,Last Name,Role,Team,Bill Rate,Employment Type,Contracting Company\n"
            "Riley,Stone,Developer,Applications,,Contractor,Covendis\n"
        ).encode()

        result = import_team_members(db, filename="team.csv", content=csv_content)

        assert result["created"] == 0
        assert result["failed"] == 1
        assert result["errors"][0]["message"] == "Bill Rate is required for contractors"


def test_mock_sync_tracks_run_and_unmapped_references():
    with session() as db:
        _seed_buckets(db)
        _add_mock_sync_mappings(db)

        result = run_mock_jira_rovo_sync(db)

        assert result["imported_worklogs"] == 6
        assert result["skipped_unmapped_worklogs"] == 1
        assert db.scalar(select(SyncRun).where(SyncRun.status == "completed")) is not None
        assert db.scalars(select(ActualEntry)).all()


def test_mock_sync_imports_after_mapping_unmapped_references():
    with session() as db:
        _seed_buckets(db)
        products, members = _add_mock_sync_mappings(db)
        first = run_mock_jira_rovo_sync(db)
        unmapped_user = first["unmapped_users"][0]
        map_jira_user(db, unmapped_user["id"], members["Avery Johnson"].id)
        db.add(
            ProductJiraSpace(
                product_id=products["Student Information"].id,
                jira_project_key="GRN",
                jira_project_name="Grants Portal",
                is_active=True,
            )
        )
        second = run_mock_jira_rovo_sync(db)

        assert second["skipped_unmapped_worklogs"] == 0
        assert len(db.scalars(select(ActualEntry)).all()) == 7


def test_mock_sync_canonical_product_space_overrides_conflicting_legacy_mapping():
    with session() as db:
        _seed_buckets(db)
        products, _members = _add_mock_sync_mappings(db)
        wrong_product = Product(name="Wrong Product")
        db.add(wrong_product)
        db.flush()
        legacy = JiraProductMapping(
            jira_project_key="SIS",
            jira_project_name="Student Information",
            product_id=wrong_product.id,
        )
        db.add(legacy)
        db.flush()

        run_mock_jira_rovo_sync(db)

        sis_actuals = db.scalars(select(ActualEntry).where(ActualEntry.source_project_key == "SIS")).all()
        assert sis_actuals
        assert {entry.product_id for entry in sis_actuals} == {products["Student Information"].id}
        assert legacy.product_id == products["Student Information"].id


def test_live_sync_uses_product_jira_space_mapping(monkeypatch):
    with session() as db:
        _seed_buckets(db)
        product = Product(name="Live Product")
        member = TeamMember(name="Live User", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add(
            ProductJiraSpace(
                product_id=product.id,
                jira_project_key="LIVE",
                jira_project_name="Live Jira Project",
                is_active=True,
                validation_status="valid",
            )
        )
        db.add(
            JiraUserMapping(
                jira_account_id="acct-live",
                jira_display_name="Live User",
                team_member_id=member.id,
            )
        )
        db.flush()

        monkeypatch.setattr("app.services.jira_rovo.current_live_sync_fiscal_year", lambda: 2026)
        monkeypatch.setattr(
            "app.services.jira_rovo.fetch_live_jira_worklogs",
            lambda _db, _fiscal_year: [
                MockWorklog(
                    "live-wl-1",
                    "900001",
                    "LIVE-1",
                    "Real Jira worklog",
                    "Done",
                    "LIVE",
                    "Live Jira Project",
                    "acct-live",
                    "Live User",
                    None,
                    "MAINTENANCE",
                    date(2026, 5, 6),
                    Decimal("3.50"),
                )
            ],
        )

        result = run_live_jira_rovo_sync(db, 2026)
        actual = db.scalar(select(ActualEntry).where(ActualEntry.source == "jira"))

        assert result["imported_worklogs"] == 1
        assert result["skipped_unmapped_worklogs"] == 0
        assert actual is not None
        assert actual.product_id == product.id
        assert actual.team_member_id == member.id


def test_live_sync_ignores_requested_year_and_uses_current_fiscal_year(monkeypatch):
    with session() as db:
        seen_fiscal_years: list[int] = []

        monkeypatch.setattr("app.services.jira_rovo.current_live_sync_fiscal_year", lambda: 2027)
        monkeypatch.setattr(
            "app.services.jira_rovo.fetch_live_jira_worklogs",
            lambda _db, fiscal_year: seen_fiscal_years.append(fiscal_year) or [],
        )

        result = run_live_jira_rovo_sync(db, 2026)

        assert seen_fiscal_years == [2027]
        assert result["fiscal_year"] == 2027
        assert result["requested_fiscal_year"] == 2026
        assert result["uses_current_fiscal_year"] is True


def test_live_sync_deletes_jira_actuals_for_removed_worklogs(monkeypatch):
    with session() as db:
        _seed_buckets(db)
        product = Product(name="Live Product")
        member = TeamMember(name="Live User", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add(
            ProductJiraSpace(
                product_id=product.id,
                jira_project_key="LIVE",
                jira_project_name="Live Jira Project",
                is_active=True,
                validation_status="valid",
            )
        )
        db.add(
            JiraUserMapping(
                jira_account_id="acct-live",
                jira_display_name="Live User",
                team_member_id=member.id,
            )
        )
        db.flush()
        current_worklogs = [
            MockWorklog(
                "live-wl-1",
                "900001",
                "LIVE-1",
                "First worklog",
                "Done",
                "LIVE",
                "Live Jira Project",
                "acct-live",
                "Live User",
                None,
                "MAINTENANCE",
                date(2026, 5, 6),
                Decimal("3.50"),
            ),
            MockWorklog(
                "live-wl-2",
                "900002",
                "LIVE-2",
                "Deleted later",
                "Done",
                "LIVE",
                "Live Jira Project",
                "acct-live",
                "Live User",
                None,
                "MAINTENANCE",
                date(2026, 5, 7),
                Decimal("2.00"),
            ),
        ]

        monkeypatch.setattr("app.services.jira_rovo.current_live_sync_fiscal_year", lambda: 2026)
        monkeypatch.setattr("app.services.jira_rovo.fetch_live_jira_worklogs", lambda _db, _fiscal_year: current_worklogs)
        first = run_live_jira_rovo_sync(db, 2026)
        current_worklogs = current_worklogs[:1]
        second = run_live_jira_rovo_sync(db, 2026)
        remaining = db.scalars(select(ActualEntry).where(ActualEntry.source == "jira").order_by(ActualEntry.source_worklog_id)).all()

        assert first["imported_worklogs"] == 2
        assert first["deleted_worklogs"] == 0
        assert second["imported_worklogs"] == 1
        assert second["deleted_worklogs"] == 1
        assert [entry.source_worklog_id for entry in remaining] == ["live-wl-1"]


def test_live_sync_skips_unclassified_work_type_and_deletes_existing_actual(monkeypatch):
    with session() as db:
        _seed_buckets(db)
        product = Product(name="Live Product")
        member = TeamMember(name="Live User", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        db.add(
            ProductJiraSpace(
                product_id=product.id,
                jira_project_key="LIVE",
                jira_project_name="Live Jira Project",
                is_active=True,
                validation_status="valid",
            )
        )
        db.add(
            JiraUserMapping(
                jira_account_id="acct-live",
                jira_display_name="Live User",
                team_member_id=member.id,
            )
        )
        db.flush()
        current_worklogs = [
            MockWorklog(
                "live-wl-1",
                "900001",
                "LIVE-1",
                "Classified worklog",
                "Done",
                "LIVE",
                "Live Jira Project",
                "acct-live",
                "Live User",
                None,
                "MAINTENANCE",
                date(2026, 5, 6),
                Decimal("3.50"),
            )
        ]

        monkeypatch.setattr("app.services.jira_rovo.current_live_sync_fiscal_year", lambda: 2026)
        monkeypatch.setattr("app.services.jira_rovo.fetch_live_jira_worklogs", lambda _db, _fiscal_year: current_worklogs)
        first = run_live_jira_rovo_sync(db, 2026)
        current_worklogs = [
            MockWorklog(
                "live-wl-1",
                "900001",
                "LIVE-1",
                "Unclassified worklog",
                "Done",
                "LIVE",
                "Live Jira Project",
                "acct-live",
                "Live User",
                None,
                None,
                date(2026, 5, 6),
                Decimal("3.50"),
            )
        ]
        second = run_live_jira_rovo_sync(db, 2026)

        assert first["imported_worklogs"] == 1
        assert second["imported_worklogs"] == 0
        assert second["skipped_unmapped_worklogs"] == 1
        assert second["deleted_worklogs"] == 1
        assert db.scalar(select(ActualEntry).where(ActualEntry.source_worklog_id == "live-wl-1")) is None


def test_jira_work_type_bucket_classifier_does_not_default_to_maintenance():
    assert _bucket_code_from_issue_fields({"customfield_1": {"value": "Net New"}}, ["customfield_1"]) == "NET_NEW"
    assert _bucket_code_from_issue_fields({"customfield_1": {"value": "Core Infrastructure"}}, ["customfield_1"]) is None
    assert _bucket_code_from_issue_fields({}, ["customfield_1"]) is None


def test_live_sync_retains_actual_history_after_project_mapping_changes(monkeypatch):
    with session() as db:
        _seed_buckets(db)
        product = Product(name="Live Product")
        member = TeamMember(name="Live User", role="Engineer", team="Applications", bill_rate=Decimal("100"))
        db.add_all([product, member])
        db.flush()
        bucket = db.scalar(select(Bucket).where(Bucket.code == "MAINTENANCE"))
        assert bucket is not None
        fiscal_month = get_fiscal_month(db, 2027, 1)
        db.add(
            ProductJiraSpace(
                product_id=product.id,
                jira_project_key="CURRENT",
                jira_project_name="Current Jira Project",
                is_active=True,
                validation_status="valid",
            )
        )
        db.add(
            ActualEntry(
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=fiscal_month.id,
                hours=Decimal("1.00"),
                source="jira",
                source_issue_id="900266",
                source_ticket_key="TNSD-266",
                source_worklog_id="deleted-wl-266",
                source_account_id="acct-live",
                source_project_key="TNSD",
                worked_on=date(2026, 7, 1),
            )
        )
        db.flush()

        monkeypatch.setattr("app.services.jira_rovo.current_live_sync_fiscal_year", lambda: 2027)
        monkeypatch.setattr("app.services.jira_rovo.fetch_live_jira_worklogs", lambda _db, _fiscal_year: [])

        result = run_live_jira_rovo_sync(db, 2027)
        remaining = db.scalars(select(ActualEntry).where(ActualEntry.source == "jira")).all()

        assert result["deleted_worklogs"] == 0
        assert len(remaining) == 1


def _add_mock_sync_mappings(db: Session) -> tuple[dict[str, Product], dict[str, TeamMember]]:
    products = {
        "Student Information": Product(name="Student Information", jira_space_key="SIS"),
        "Educator Licensing": Product(name="Educator Licensing", jira_space_key="EDL"),
        "Data Warehouse": Product(name="Data Warehouse", jira_space_key="DWH"),
    }
    members = {
        "Avery Johnson": TeamMember(name="Avery Johnson", role="Product Engineer", team="Applications", bill_rate=Decimal("115")),
        "Morgan Lee": TeamMember(name="Morgan Lee", role="Business Analyst", team="Product", bill_rate=Decimal("95")),
        "Sam Patel": TeamMember(name="Sam Patel", role="Systems Analyst", team="Operations", bill_rate=Decimal("105")),
        "Riley Chen": TeamMember(name="Riley Chen", role="Data Engineer", team="Data Services", bill_rate=Decimal("125")),
        "Jordan Smith": TeamMember(name="Jordan Smith", role="QA Analyst", team="Quality", bill_rate=Decimal("88")),
    }
    db.add_all([*products.values(), *members.values()])
    db.flush()

    for jira_key, product_name in {"SIS": "Student Information", "EDL": "Educator Licensing", "DWH": "Data Warehouse"}.items():
        db.add(
            ProductJiraSpace(
                jira_project_key=jira_key,
                jira_project_name=product_name,
                product_id=products[product_name].id,
            )
        )

    for account_id, member_name in {
        "acct-avery": "Avery Johnson",
        "acct-morgan": "Morgan Lee",
        "acct-sam": "Sam Patel",
        "acct-riley": "Riley Chen",
        "acct-jordan": "Jordan Smith",
    }.items():
        db.add(
            JiraUserMapping(
                jira_account_id=account_id,
                jira_display_name=member_name,
                jira_email=f"{member_name.split()[0].lower()}@example.test",
                team_member_id=members[member_name].id,
            )
        )

    db.flush()
    return products, members
