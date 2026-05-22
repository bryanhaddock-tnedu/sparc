from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.seed import _seed_buckets
from app.models import ActualEntry, Base, Bucket, ForecastEntry, JiraUserMapping, Product, ProductBudget, ProductJiraSpace, ProductTeamMember, TeamMember
from app.services.admin_data import build_admin_data_archive, import_admin_data_content
from app.services.forecasting import upsert_forecast_entry


def test_admin_data_export_imports_owned_data_and_excludes_jira_refresh_data():
    source_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(source_engine)

    with Session(source_engine) as source_db:
        _seed_buckets(source_db)
        product = Product(name="SWORD", jira_space_key="SWRD", budget_amount=Decimal("0.00"))
        member = TeamMember(
            staff_id="TM-1",
            name="Avery Johnson",
            role="Dev",
            team="Product Maintenance",
            bill_rate=Decimal("100.00"),
            employment_type="Contractor",
            contracting_company="Acme",
        )
        source_db.add_all([product, member])
        source_db.flush()
        source_db.add(ProductBudget(product_id=product.id, fiscal_year=2027, budget_amount=Decimal("250000.00")))
        source_db.add(ProductTeamMember(product_id=product.id, team_member_id=member.id, status="active"))
        source_db.add(ProductJiraSpace(product_id=product.id, jira_project_key="SWRD", jira_project_name="SWORD", validation_status="valid"))
        source_db.add(JiraUserMapping(jira_account_id="abc-123", jira_display_name="Avery Jira", team_member_id=member.id))

        forecast = upsert_forecast_entry(
            source_db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=Decimal("42"),
        )
        bucket = source_db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        source_db.add(
            ActualEntry(
                product_id=product.id,
                team_member_id=member.id,
                bucket_id=bucket.id,
                fiscal_month_id=forecast.fiscal_month_id,
                hours=Decimal("5"),
                source="live_jira",
                source_ticket_key="SWRD-1",
                source_worklog_id="10001",
            )
        )
        source_db.commit()

        export = build_admin_data_archive(source_db)
        content = export.getvalue()

    with ZipFile(BytesIO(content)) as archive:
        file_names = archive.namelist()
        assert "manifest.json" in file_names
        assert "team_members.csv" in file_names
        assert "forecast_entries.csv" in file_names
        assert "actual_entries.csv" not in file_names
        assert "sync_runs.csv" not in file_names
        assert "jira_project_catalog.csv" not in file_names

    target_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(target_engine)
    with Session(target_engine) as target_db:
        _seed_buckets(target_db)
        result = import_admin_data_content(target_db, content, "sparc-admin-data.zip")
        target_db.commit()

        imported_product = target_db.scalar(select(Product).where(Product.name == "SWORD"))
        imported_member = target_db.scalar(select(TeamMember).where(TeamMember.name == "Avery Johnson"))
        imported_forecast = target_db.scalar(select(ForecastEntry))

        assert result["errors"] == []
        assert imported_product is not None
        assert imported_member is not None
        assert target_db.scalar(select(ProductBudget).where(ProductBudget.product_id == imported_product.id)).budget_amount == Decimal("250000.00")
        assert target_db.scalar(select(ProductJiraSpace).where(ProductJiraSpace.jira_project_key == "SWRD")).product_id == imported_product.id
        assert target_db.scalar(select(JiraUserMapping).where(JiraUserMapping.jira_account_id == "abc-123")).team_member_id == imported_member.id
        assert imported_forecast is not None
        assert imported_forecast.hours == Decimal("42.00")
        assert target_db.scalar(select(ActualEntry)) is None
