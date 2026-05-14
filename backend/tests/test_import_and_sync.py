from io import BytesIO
from decimal import Decimal

from openpyxl import Workbook
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.seed import _seed_buckets, _seed_jira_mappings, _seed_products, _seed_team_members
from app.models import ActualEntry, Base, SyncRun, TeamMember
from app.services.jira_rovo import map_jira_product, map_jira_user, run_mock_jira_rovo_sync
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
        products = _seed_products(db)
        members = _seed_team_members(db)
        _seed_jira_mappings(db, products, members)

        result = run_mock_jira_rovo_sync(db)

        assert result["imported_worklogs"] == 6
        assert result["skipped_unmapped_worklogs"] == 1
        assert db.scalar(select(SyncRun).where(SyncRun.status == "completed")) is not None
        assert db.scalars(select(ActualEntry)).all()


def test_mock_sync_imports_after_mapping_unmapped_references():
    with session() as db:
        _seed_buckets(db)
        products = _seed_products(db)
        members = _seed_team_members(db)
        _seed_jira_mappings(db, products, members)
        first = run_mock_jira_rovo_sync(db)
        unmapped_user = first["unmapped_users"][0]
        unmapped_product = first["unmapped_products"][0]

        map_jira_user(db, unmapped_user["id"], members["Avery Johnson"].id)
        map_jira_product(db, unmapped_product["id"], products["Student Information"].id)
        second = run_mock_jira_rovo_sync(db)

        assert second["skipped_unmapped_worklogs"] == 0
        assert len(db.scalars(select(ActualEntry)).all()) == 7
