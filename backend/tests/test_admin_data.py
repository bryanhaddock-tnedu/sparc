import json
from decimal import Decimal
from io import BytesIO
from zipfile import ZipFile

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.seed import _seed_buckets
from app.models import (
    ActualEntry,
    AppUser,
    Base,
    Bucket,
    EstimationProfile,
    ForecastEntry,
    JiraUserMapping,
    Product,
    ProductBudget,
    ProductJiraSpace,
    ProductTeamMember,
    RoadmapItem,
    RoadmapItemIssueLink,
    TeamMember,
)
from app.services.access_control import UserRole, create_app_user, get_app_user_by_email
from app.services.admin_data import build_admin_data_archive, import_admin_data_content
from app.services.estimation_policy import ensure_default_estimation_profile
from app.services.forecasting import upsert_forecast_entry
from app.services.roadmap import MANUAL_ROADMAP_LINK_SOURCE


def test_admin_data_export_imports_owned_data_and_excludes_jira_refresh_data():
    source_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(source_engine)

    with Session(source_engine) as source_db:
        _seed_buckets(source_db)
        ensure_default_estimation_profile(source_db)
        product = Product(
            name="SWORD",
            jira_space_key="SWRD",
            office="Operations",
            division="IT",
            budget_amount=Decimal("0.00"),
        )
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
        bucket = source_db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))
        roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            product_id=product.id,
            bucket_id=bucket.id,
            product_mapping_source="manual",
            bucket_mapping_source="manual",
            jira_issue_id="10001",
            jira_issue_key="ROADMAP-1",
            title="SWORD modernization",
            issue_type="Idea",
        )
        source_db.add(roadmap_item)
        source_db.flush()
        source_db.add(
            RoadmapItemIssueLink(
                roadmap_item_id=roadmap_item.id,
                product_id=product.id,
                jira_issue_key="SWRD-1",
                jira_project_key="SWRD",
                source=MANUAL_ROADMAP_LINK_SOURCE,
            )
        )

        forecast = upsert_forecast_entry(
            source_db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code="NET_NEW",
            fiscal_year=2027,
            month_sequence=1,
            hours=Decimal("42"),
        )
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
        assert "roadmap_item_overrides.csv" in file_names
        assert "roadmap_ticket_mappings.csv" in file_names
        assert "user_access.csv" not in file_names
        assert "estimation_profiles.csv" in file_names
        assert "actual_entries.csv" not in file_names
        assert "sync_runs.csv" not in file_names
        assert "jira_project_catalog.csv" not in file_names
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["version"] == 2
        assert manifest["package_id"]
        assert manifest["row_counts"]["forecast_entries"] == 1
        assert manifest["row_counts"]["roadmap_item_overrides"] == 1

    target_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(target_engine)
    with Session(target_engine) as target_db:
        _seed_buckets(target_db)
        result = import_admin_data_content(target_db, content, "sparc-admin-data.zip")
        target_db.commit()

        imported_product = target_db.scalar(select(Product).where(Product.name == "SWORD"))
        imported_member = target_db.scalar(select(TeamMember).where(TeamMember.name == "Avery Johnson"))
        imported_forecast = target_db.scalar(select(ForecastEntry))
        imported_bucket = target_db.scalar(select(Bucket).where(Bucket.code == "NET_NEW"))

        assert result["errors"] == []
        assert imported_product is not None
        assert imported_product.office == "Operations"
        assert imported_product.division == "IT"
        assert imported_member is not None
        assert target_db.scalar(select(ProductBudget).where(ProductBudget.product_id == imported_product.id)).budget_amount == Decimal("250000.00")
        assert target_db.scalar(select(ProductJiraSpace).where(ProductJiraSpace.jira_project_key == "SWRD")).product_id == imported_product.id
        assert target_db.scalar(select(JiraUserMapping).where(JiraUserMapping.jira_account_id == "abc-123")).team_member_id == imported_member.id
        assert imported_forecast is not None
        assert imported_forecast.hours == Decimal("42.00")
        assert target_db.scalar(select(EstimationProfile).where(EstimationProfile.is_active.is_(True))) is not None
        assert target_db.scalar(select(ActualEntry)) is None
        assert result["package"]["version"] == 2
        assert len(result["warnings"]) == 2

        target_roadmap_item = RoadmapItem(
            source="jira_product_discovery",
            fiscal_year=2027,
            jira_issue_id="20001",
            jira_issue_key="ROADMAP-1",
            title="SWORD modernization",
            issue_type="Idea",
        )
        target_db.add(target_roadmap_item)
        target_db.flush()
        overlay_result = import_admin_data_content(
            target_db,
            content,
            "sparc-admin-data.zip",
            ["roadmap_item_overrides", "roadmap_ticket_mappings"],
        )
        target_db.commit()
        target_db.refresh(target_roadmap_item)

        assert overlay_result["errors"] == []
        assert overlay_result["warnings"] == []
        assert target_roadmap_item.product_id == imported_product.id
        assert target_roadmap_item.bucket_id == imported_bucket.id
        assert target_roadmap_item.product_mapping_source == "manual"
        assert target_roadmap_item.bucket_mapping_source == "manual"
        imported_link = target_db.scalar(
            select(RoadmapItemIssueLink).where(RoadmapItemIssueLink.jira_issue_key == "SWRD-1")
        )
        assert imported_link is not None
        assert imported_link.roadmap_item_id == target_roadmap_item.id
        assert imported_link.source == MANUAL_ROADMAP_LINK_SOURCE


def test_user_access_export_is_optional_sanitized_and_preserves_target_authentication():
    source_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(source_engine)
    with Session(source_engine) as source_db:
        create_app_user(
            source_db,
            email="florie@tnedu.gov",
            display_name="Florie",
            role=UserRole.PROGRAM_AREA_VIEW_ONLY.value,
            program_areas=["Academics", "Programs"],
            temporary_password="stage-only-password",
        )
        create_app_user(
            source_db,
            email="existing@tnedu.gov",
            display_name="Existing User",
            role=UserRole.LEADERSHIP_VIEW_ONLY.value,
        )
        source_db.commit()
        content = build_admin_data_archive(source_db, ["user_access"]).getvalue()

    target_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(target_engine)
    with Session(target_engine) as target_db:
        existing = create_app_user(
            target_db,
            email="existing@tnedu.gov",
            display_name="Existing Admin",
            role=UserRole.ADMIN.value,
            temporary_password="production-password",
        )
        existing_password_hash = existing.password_hash
        target_db.commit()

        result = import_admin_data_content(target_db, content, "sparc-admin-data.zip", ["user_access"])
        target_db.commit()

        imported = get_app_user_by_email(target_db, "florie@tnedu.gov")
        preserved = get_app_user_by_email(target_db, "existing@tnedu.gov")
        assert imported is not None
        assert imported.role == UserRole.PROGRAM_AREA_VIEW_ONLY.value
        assert sorted(assignment.program_area for assignment in imported.program_area_assignments) == ["Academics", "Programs"]
        assert imported.local_login_enabled is False
        assert imported.password_hash is None
        assert preserved is not None
        assert preserved.role == UserRole.ADMIN.value
        assert preserved.password_hash == existing_password_hash
        assert result["datasets"][0]["created"] == 1
        assert result["datasets"][0]["failed"] == 1
        assert "final active SPARC Admin" in result["errors"][0]["message"]
        assert len(result["warnings"]) == 1


def test_admin_data_import_never_uses_source_database_ids_as_target_identity():
    source_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(source_engine)
    with Session(source_engine) as source_db:
        source_db.add_all([Product(name="Alpha"), Product(name="Bravo")])
        source_db.commit()
        content = build_admin_data_archive(source_db, ["products"]).getvalue()

    target_engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(target_engine)
    with Session(target_engine) as target_db:
        target_db.add_all([Product(name="Bravo"), Product(name="Charlie")])
        target_db.commit()
        bravo_id = target_db.scalar(select(Product.id).where(Product.name == "Bravo"))
        charlie_id = target_db.scalar(select(Product.id).where(Product.name == "Charlie"))

        result = import_admin_data_content(target_db, content, "sparc-admin-data.zip", ["products"])
        target_db.commit()

        assert result["errors"] == []
        assert target_db.scalar(select(Product.id).where(Product.name == "Bravo")) == bravo_id
        assert target_db.scalar(select(Product.id).where(Product.name == "Charlie")) == charlie_id
        assert target_db.scalar(select(Product.id).where(Product.name == "Alpha")) not in {bravo_id, charlie_id}
