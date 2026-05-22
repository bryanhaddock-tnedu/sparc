from io import BytesIO
from datetime import date
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.seed import _seed_buckets
from app.models import ActualEntry, Base, JiraProductMapping, JiraUserMapping, Product, ProductJiraSpace, SyncRun, TeamMember
from app.services.jira_rovo import MockWorklog, map_jira_product, map_jira_user, run_live_jira_rovo_sync, run_mock_jira_rovo_sync
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
        unmapped_product = first["unmapped_products"][0]

        map_jira_user(db, unmapped_user["id"], members["Avery Johnson"].id)
        map_jira_product(db, unmapped_product["id"], products["Student Information"].id)
        second = run_mock_jira_rovo_sync(db)

        assert second["skipped_unmapped_worklogs"] == 0
        assert len(db.scalars(select(ActualEntry)).all()) == 7


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
            JiraProductMapping(
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
