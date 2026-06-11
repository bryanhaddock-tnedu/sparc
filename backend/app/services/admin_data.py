from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO, StringIO
from typing import Iterable
from zipfile import BadZipFile, ZipFile, ZIP_DEFLATED

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Bucket,
    FiscalMonth,
    ForecastEntry,
    JiraProductMapping,
    JiraUserMapping,
    Product,
    ProductBudget,
    ProductJiraSpace,
    ProductTeamMember,
    TeamMember,
)
from app.services.fiscal_year import ensure_fiscal_months
from app.services.forecasting import upsert_forecast_entry


@dataclass(frozen=True)
class AdminDataSet:
    key: str
    label: str
    sheet_name: str
    description: str
    default_selected: bool = True

    @property
    def csv_file_name(self) -> str:
        return f"{self.key}.csv"


EXPORT_DATASETS: tuple[AdminDataSet, ...] = (
    AdminDataSet("buckets", "Buckets", "Buckets", "Reference work buckets used by forecast and actual records."),
    AdminDataSet("team_members", "Team Members", "TeamMembers", "Roster, rates, employment type, and status."),
    AdminDataSet("products", "Products", "Products", "SPARC products and product-level details."),
    AdminDataSet("product_budgets", "Product Budgets", "ProductBudgets", "Fiscal-year-specific product budgets."),
    AdminDataSet("product_team_members", "Product Team Members", "ProductTeamMembers", "Manual product team assignments."),
    AdminDataSet("product_jira_spaces", "Product Jira Spaces", "ProductJiraSpaces", "Manual SPARC product-to-Jira project mappings."),
    AdminDataSet("jira_user_mappings", "Jira User Mappings", "JiraUserMappings", "Manual Jira user-to-roster mappings."),
    AdminDataSet("jira_product_mappings", "Jira Product Mappings", "JiraProductMappings", "Legacy Jira project-to-product mappings."),
    AdminDataSet("forecast_entries", "Forecast Entries", "ForecastEntries", "Manager-entered planning hours by product, person, bucket, and month."),
)

EXCLUDED_JIRA_REFRESH_DATA = (
    "ActualEntry Jira worklogs",
    "SyncRun history",
    "JiraProjectCatalog refresh snapshots",
    "EstimatedEntry generated estimates",
    "EstimationRun history",
    "EstimatedIssueAllocation audit rows",
)

_DATASET_BY_KEY = {dataset.key: dataset for dataset in EXPORT_DATASETS}
_SHEET_TO_DATASET_KEY = {dataset.sheet_name: dataset.key for dataset in EXPORT_DATASETS}
_CSV_TO_DATASET_KEY = {dataset.csv_file_name: dataset.key for dataset in EXPORT_DATASETS}


def export_options() -> list[dict[str, object]]:
    return [
        {
            "key": dataset.key,
            "label": dataset.label,
            "description": dataset.description,
            "default_selected": dataset.default_selected,
        }
        for dataset in EXPORT_DATASETS
    ]


def normalize_dataset_keys(dataset_keys: Iterable[str] | None) -> list[str]:
    keys = [key for key in (dataset_keys or []) if key]
    if not keys:
        return [dataset.key for dataset in EXPORT_DATASETS if dataset.default_selected]
    unknown = sorted(set(keys) - set(_DATASET_BY_KEY))
    if unknown:
        raise ValueError(f"Unknown admin data set: {', '.join(unknown)}")
    return [dataset.key for dataset in EXPORT_DATASETS if dataset.key in keys]


def build_admin_data_export(db: Session, dataset_keys: Iterable[str] | None = None) -> BytesIO:
    selected_keys = normalize_dataset_keys(dataset_keys)
    workbook = Workbook()
    manifest = workbook.active
    manifest.title = "Manifest"
    _write_manifest(manifest, selected_keys)

    writers = {
        "buckets": _write_buckets,
        "team_members": _write_team_members,
        "products": _write_products,
        "product_budgets": _write_product_budgets,
        "product_team_members": _write_product_team_members,
        "product_jira_spaces": _write_product_jira_spaces,
        "jira_user_mappings": _write_jira_user_mappings,
        "jira_product_mappings": _write_jira_product_mappings,
        "forecast_entries": _write_forecast_entries,
    }

    for key in selected_keys:
        writers[key](workbook, db)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def build_admin_data_archive(db: Session, dataset_keys: Iterable[str] | None = None) -> BytesIO:
    selected_keys = normalize_dataset_keys(dataset_keys)
    workbook = load_workbook(build_admin_data_export(db, selected_keys), data_only=True)
    generated_at = datetime.now(timezone.utc).isoformat()

    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        manifest = {
            "export_type": "SPARC_ADMIN_DATA_PACKAGE",
            "version": 1,
            "format": "zip-csv",
            "generated_at": generated_at,
            "included_datasets": selected_keys,
            "excluded_jira_refresh_data": list(EXCLUDED_JIRA_REFRESH_DATA),
            "files": {key: _DATASET_BY_KEY[key].csv_file_name for key in selected_keys},
        }
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))

        for key in selected_keys:
            dataset = _DATASET_BY_KEY[key]
            sheet = workbook[dataset.sheet_name]
            csv_buffer = StringIO()
            writer = csv.writer(csv_buffer, lineterminator="\n")
            for values in sheet.iter_rows(values_only=True):
                writer.writerow(["" if value is None else value for value in values])
            archive.writestr(dataset.csv_file_name, csv_buffer.getvalue())

    output.seek(0)
    return output


def build_admin_data_json_package(db: Session, dataset_keys: Iterable[str] | None = None) -> dict[str, object]:
    selected_keys = normalize_dataset_keys(dataset_keys)
    workbook = load_workbook(build_admin_data_export(db, selected_keys), data_only=True)
    data: dict[str, object] = {}
    for key in selected_keys:
        dataset = _DATASET_BY_KEY[key]
        sheet = workbook[dataset.sheet_name]
        headers = [str(cell.value or "").strip() for cell in sheet[1]]
        rows = []
        for values in sheet.iter_rows(min_row=2, values_only=True):
            if all(value is None or value == "" for value in values):
                continue
            rows.append({headers[index]: value for index, value in enumerate(values) if index < len(headers)})
        data[key] = {
            "label": dataset.label,
            "sheet_name": dataset.sheet_name,
            "headers": headers,
            "rows": rows,
        }
    return {
        "export_type": "SPARC_ADMIN_DATA_PACKAGE",
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "included_datasets": selected_keys,
        "excluded_jira_refresh_data": list(EXCLUDED_JIRA_REFRESH_DATA),
        "data": data,
    }


def import_admin_data_package(db: Session, content: bytes, dataset_keys: Iterable[str] | None = None) -> dict[str, object]:
    workbook = load_workbook(BytesIO(content), data_only=True)
    selected_keys = normalize_dataset_keys(dataset_keys)
    available_keys = [_SHEET_TO_DATASET_KEY[name] for name in workbook.sheetnames if name in _SHEET_TO_DATASET_KEY]
    keys_to_import = [key for key in selected_keys if key in available_keys]

    results = {key: {"key": key, "label": _DATASET_BY_KEY[key].label, "created": 0, "updated": 0, "skipped": 0, "failed": 0} for key in keys_to_import}
    errors: list[dict[str, object]] = []

    importers = {
        "buckets": _import_buckets,
        "team_members": _import_team_members,
        "products": _import_products,
        "product_budgets": _import_product_budgets,
        "product_team_members": _import_product_team_members,
        "product_jira_spaces": _import_product_jira_spaces,
        "jira_user_mappings": _import_jira_user_mappings,
        "jira_product_mappings": _import_jira_product_mappings,
        "forecast_entries": _import_forecast_entries,
    }

    # Dependencies matter: references first, then relationships, then forecast facts.
    for key in [dataset.key for dataset in EXPORT_DATASETS if dataset.key in keys_to_import]:
        importers[key](db, workbook, results[key], errors)
        db.flush()

    return {
        "datasets": list(results.values()),
        "errors": errors,
        "excluded_jira_refresh_data": list(EXCLUDED_JIRA_REFRESH_DATA),
    }


def import_admin_data_archive(db: Session, content: bytes, dataset_keys: Iterable[str] | None = None) -> dict[str, object]:
    try:
        archive = ZipFile(BytesIO(content))
    except BadZipFile as exc:
        raise ValueError("Admin data package must be a SPARC zip export or .xlsx workbook") from exc

    with archive:
        manifest = _read_archive_manifest(archive)
        selected_keys = normalize_dataset_keys(dataset_keys or manifest.get("included_datasets"))
        workbook = Workbook()
        workbook.active.title = "Manifest"

        for key in selected_keys:
            dataset = _DATASET_BY_KEY[key]
            if dataset.csv_file_name not in archive.namelist():
                continue
            sheet = workbook.create_sheet(dataset.sheet_name)
            text = archive.read(dataset.csv_file_name).decode("utf-8-sig")
            for row in csv.reader(StringIO(text)):
                sheet.append(row)

        output = BytesIO()
        workbook.save(output)
        output.seek(0)
        return import_admin_data_package(db, output.getvalue(), selected_keys)


def import_admin_data_json_package(db: Session, content: bytes, dataset_keys: Iterable[str] | None = None) -> dict[str, object]:
    try:
        package = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("JSON admin data package could not be parsed") from exc

    selected_keys = normalize_dataset_keys(dataset_keys or package.get("included_datasets"))
    data = package.get("data")
    if not isinstance(data, dict):
        raise ValueError("JSON admin data package is missing data")

    workbook = Workbook()
    manifest = workbook.active
    manifest.title = "Manifest"
    _write_manifest(manifest, selected_keys)

    for key in selected_keys:
        dataset = _DATASET_BY_KEY[key]
        section = data.get(key)
        if not isinstance(section, dict):
            continue
        rows = section.get("rows", [])
        headers = section.get("headers", [])
        if not headers and isinstance(rows, list) and rows:
            headers = list(rows[0].keys())
        if not isinstance(headers, list):
            raise ValueError(f"JSON admin data package has invalid headers for {dataset.label}")
        if not isinstance(rows, list):
            raise ValueError(f"JSON admin data package has invalid rows for {dataset.label}")
        sheet = workbook.create_sheet(dataset.sheet_name)
        sheet.append(headers)
        for row in rows:
            if not isinstance(row, dict):
                continue
            sheet.append([row.get(header) for header in headers])
        _style_sheet(sheet)

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return import_admin_data_package(db, output.getvalue(), selected_keys)


def import_admin_data_content(db: Session, content: bytes, filename: str | None = None, dataset_keys: Iterable[str] | None = None) -> dict[str, object]:
    lower_name = (filename or "").lower()
    if lower_name.endswith(".zip"):
        return import_admin_data_archive(db, content, dataset_keys)
    if lower_name.endswith(".json") or content.lstrip().startswith(b"{"):
        return import_admin_data_json_package(db, content, dataset_keys)
    if not lower_name.endswith(".xlsx") and content.startswith(b"PK"):
        try:
            with ZipFile(BytesIO(content)) as archive:
                if "manifest.json" in archive.namelist() or any(name in _CSV_TO_DATASET_KEY for name in archive.namelist()):
                    return import_admin_data_archive(db, content, dataset_keys)
        except BadZipFile:
            pass
    return import_admin_data_package(db, content, dataset_keys)


def _read_archive_manifest(archive: ZipFile) -> dict[str, object]:
    if "manifest.json" not in archive.namelist():
        return {"included_datasets": [_CSV_TO_DATASET_KEY[name] for name in archive.namelist() if name in _CSV_TO_DATASET_KEY]}
    try:
        return json.loads(archive.read("manifest.json").decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Admin data package manifest could not be parsed") from exc


def _write_manifest(sheet, selected_keys: list[str]) -> None:
    rows = [
        ("Export Type", "SPARC admin data package"),
        ("Generated At", datetime.now(timezone.utc).isoformat()),
        ("Included Data Sets", ", ".join(_DATASET_BY_KEY[key].label for key in selected_keys)),
        ("Excluded Jira Refresh Data", ", ".join(EXCLUDED_JIRA_REFRESH_DATA)),
        ("Import Rule", "Rows are importable by natural keys like product name, team member name, Jira key, bucket code, fiscal year, and month sequence."),
        ("Note", "Use Jira Sync in SPARC to repopulate actual worklogs and Jira refresh data after importing this package."),
    ]
    _append_sheet_rows(sheet, ("Field", "Value"), rows)
    sheet.column_dimensions["A"].width = 28
    sheet.column_dimensions["B"].width = 140


def _write_buckets(workbook: Workbook, db: Session) -> None:
    rows = ((bucket.id, bucket.code, bucket.name) for bucket in db.scalars(select(Bucket).order_by(Bucket.id)).all())
    _append_sheet(workbook, "Buckets", ("source_bucket_id", "code", "name"), rows)


def _write_team_members(workbook: Workbook, db: Session) -> None:
    members = db.scalars(select(TeamMember).order_by(TeamMember.name)).all()
    rows = (
        (
            member.id,
            member.staff_id,
            member.name,
            member.role,
            member.team,
            _number(member.bill_rate),
            member.employment_type,
            member.contracting_company,
            member.status,
            _iso(member.created_at),
            _iso(member.updated_at),
        )
        for member in members
    )
    _append_sheet(
        workbook,
        "TeamMembers",
        (
            "source_team_member_id",
            "staff_id",
            "name",
            "role",
            "team",
            "bill_rate",
            "employment_type",
            "contracting_company",
            "status",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _write_products(workbook: Workbook, db: Session) -> None:
    products = db.scalars(select(Product).order_by(Product.name)).all()
    rows = (
        (
            product.id,
            product.name,
            product.jira_space_key,
            product.description,
            product.office,
            product.division,
            _number(product.budget_amount),
            product.is_active,
            _iso(product.created_at),
            _iso(product.updated_at),
        )
        for product in products
    )
    _append_sheet(
        workbook,
        "Products",
        (
            "source_product_id",
            "name",
            "jira_space_key",
            "description",
            "office",
            "division",
            "legacy_budget_amount",
            "is_active",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _write_product_budgets(workbook: Workbook, db: Session) -> None:
    budgets = db.scalars(
        select(ProductBudget).options(joinedload(ProductBudget.product)).join(ProductBudget.product).order_by(Product.name, ProductBudget.fiscal_year)
    ).all()
    rows = (
        (
            budget.id,
            budget.product_id,
            budget.product.name,
            budget.fiscal_year,
            _number(budget.budget_amount),
            _iso(budget.created_at),
            _iso(budget.updated_at),
        )
        for budget in budgets
    )
    _append_sheet(
        workbook,
        "ProductBudgets",
        ("source_product_budget_id", "source_product_id", "product_name", "fiscal_year", "budget_amount", "created_at", "updated_at"),
        rows,
    )


def _write_product_team_members(workbook: Workbook, db: Session) -> None:
    assignments = db.scalars(
        select(ProductTeamMember)
        .options(
            joinedload(ProductTeamMember.product),
            joinedload(ProductTeamMember.team_member),
            joinedload(ProductTeamMember.default_bucket),
        )
        .join(ProductTeamMember.product)
        .join(ProductTeamMember.team_member)
        .order_by(Product.name, TeamMember.name)
    ).all()
    rows = (
        (
            assignment.id,
            assignment.product_id,
            assignment.product.name,
            assignment.team_member_id,
            assignment.team_member.name,
            assignment.default_bucket.code if assignment.default_bucket else None,
            assignment.default_bucket.name if assignment.default_bucket else None,
            assignment.status,
            _iso(assignment.created_at),
            _iso(assignment.updated_at),
        )
        for assignment in assignments
    )
    _append_sheet(
        workbook,
        "ProductTeamMembers",
        (
            "source_assignment_id",
            "source_product_id",
            "product_name",
            "source_team_member_id",
            "team_member_name",
            "default_bucket_code",
            "default_bucket_name",
            "status",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _write_product_jira_spaces(workbook: Workbook, db: Session) -> None:
    spaces = db.scalars(
        select(ProductJiraSpace).options(joinedload(ProductJiraSpace.product)).join(ProductJiraSpace.product).order_by(Product.name, ProductJiraSpace.jira_project_key)
    ).all()
    rows = (
        (
            space.id,
            space.product_id,
            space.product.name,
            space.jira_project_catalog_id,
            space.jira_project_id,
            space.jira_project_key,
            space.jira_project_name,
            space.is_active,
            space.scope_jql,
            space.validation_status,
            space.validation_message,
            _iso(space.last_validated_at),
            _iso(space.created_at),
            _iso(space.updated_at),
        )
        for space in spaces
    )
    _append_sheet(
        workbook,
        "ProductJiraSpaces",
        (
            "source_product_jira_space_id",
            "source_product_id",
            "product_name",
            "jira_project_catalog_id",
            "jira_project_id",
            "jira_project_key",
            "jira_project_name",
            "is_active",
            "scope_jql",
            "validation_status",
            "validation_message",
            "last_validated_at",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _write_jira_user_mappings(workbook: Workbook, db: Session) -> None:
    mappings = db.scalars(
        select(JiraUserMapping).options(joinedload(JiraUserMapping.team_member)).order_by(JiraUserMapping.jira_display_name)
    ).all()
    rows = (
        (
            mapping.id,
            mapping.jira_account_id,
            mapping.jira_display_name,
            mapping.jira_email,
            mapping.team_member_id,
            mapping.team_member.name if mapping.team_member else None,
            _iso(mapping.created_at),
            _iso(mapping.updated_at),
        )
        for mapping in mappings
    )
    _append_sheet(
        workbook,
        "JiraUserMappings",
        (
            "source_jira_user_mapping_id",
            "jira_account_id",
            "jira_display_name",
            "jira_email",
            "source_team_member_id",
            "team_member_name",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _write_jira_product_mappings(workbook: Workbook, db: Session) -> None:
    mappings = db.scalars(
        select(JiraProductMapping).options(joinedload(JiraProductMapping.product)).order_by(JiraProductMapping.jira_project_key)
    ).all()
    rows = (
        (
            mapping.id,
            mapping.jira_project_key,
            mapping.jira_project_name,
            mapping.product_id,
            mapping.product.name if mapping.product else None,
            _iso(mapping.created_at),
            _iso(mapping.updated_at),
        )
        for mapping in mappings
    )
    _append_sheet(
        workbook,
        "JiraProductMappings",
        (
            "source_jira_product_mapping_id",
            "jira_project_key",
            "jira_project_name",
            "source_product_id",
            "product_name",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _write_forecast_entries(workbook: Workbook, db: Session) -> None:
    forecasts = db.scalars(
        select(ForecastEntry)
        .options(
            joinedload(ForecastEntry.product),
            joinedload(ForecastEntry.team_member),
            joinedload(ForecastEntry.bucket),
            joinedload(ForecastEntry.fiscal_month),
        )
        .join(ForecastEntry.product)
        .join(ForecastEntry.team_member)
        .join(ForecastEntry.bucket)
        .join(ForecastEntry.fiscal_month)
        .order_by(FiscalMonth.fiscal_year, FiscalMonth.sequence, Product.name, TeamMember.name, Bucket.name)
    ).all()
    rows = (
        (
            forecast.id,
            forecast.product_id,
            forecast.product.name,
            forecast.team_member_id,
            forecast.team_member.name,
            forecast.bucket_id,
            forecast.bucket.code,
            forecast.bucket.name,
            forecast.fiscal_month_id,
            forecast.fiscal_month.fiscal_year,
            forecast.fiscal_month.sequence,
            forecast.fiscal_month.label,
            forecast.fiscal_month.calendar_year,
            forecast.fiscal_month.calendar_month,
            _number(forecast.hours),
            _iso(forecast.created_at),
            _iso(forecast.updated_at),
        )
        for forecast in forecasts
    )
    _append_sheet(
        workbook,
        "ForecastEntries",
        (
            "source_forecast_entry_id",
            "source_product_id",
            "product_name",
            "source_team_member_id",
            "team_member_name",
            "source_bucket_id",
            "bucket_code",
            "bucket_name",
            "source_fiscal_month_id",
            "fiscal_year",
            "month_sequence",
            "month_label",
            "calendar_year",
            "calendar_month",
            "hours",
            "created_at",
            "updated_at",
        ),
        rows,
    )


def _import_buckets(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "Buckets"):
        code = _text(row, "code")
        name = _text(row, "name")
        if not code or not name:
            _fail(result, errors, "Buckets", row_number, "Bucket code and name are required")
            continue
        bucket = db.scalar(select(Bucket).where(Bucket.code == code))
        if bucket is None:
            db.add(Bucket(code=code, name=name))
            result["created"] += 1
        else:
            bucket.name = name
            result["updated"] += 1


def _import_team_members(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "TeamMembers"):
        name = _text(row, "name")
        if not name:
            _fail(result, errors, "TeamMembers", row_number, "Team member name is required")
            continue
        staff_id = _text(row, "staff_id")
        member = _find_team_member(db, row)
        created = member is None
        if member is None:
            member = TeamMember(name=name, role="", team="")
            db.add(member)
        member.staff_id = staff_id
        member.name = name
        member.role = _text(row, "role") or ""
        member.team = _text(row, "team") or ""
        member.bill_rate = _decimal(row, "bill_rate")
        member.employment_type = _text(row, "employment_type") or "Employee"
        member.contracting_company = _text(row, "contracting_company")
        member.status = _text(row, "status") or "active"
        result["created" if created else "updated"] += 1


def _import_products(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "Products"):
        name = _text(row, "name")
        if not name:
            _fail(result, errors, "Products", row_number, "Product name is required")
            continue
        product = _find_product(db, row)
        created = product is None
        if product is None:
            product = Product(name=name)
            db.add(product)
        product.name = name
        product.jira_space_key = _text(row, "jira_space_key")
        product.description = _text(row, "description")
        product.office = _text(row, "office")
        product.division = _text(row, "division")
        product.budget_amount = _decimal(row, "legacy_budget_amount")
        product.is_active = _bool(row.get("is_active"), default=True)
        result["created" if created else "updated"] += 1


def _import_product_budgets(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "ProductBudgets"):
        product = _find_product(db, row)
        fiscal_year = _int(row, "fiscal_year")
        if product is None or fiscal_year is None:
            _fail(result, errors, "ProductBudgets", row_number, "Product and fiscal year are required")
            continue
        budget = db.scalar(select(ProductBudget).where(ProductBudget.product_id == product.id, ProductBudget.fiscal_year == fiscal_year))
        created = budget is None
        if budget is None:
            budget = ProductBudget(product_id=product.id, fiscal_year=fiscal_year)
            db.add(budget)
        budget.budget_amount = _decimal(row, "budget_amount")
        result["created" if created else "updated"] += 1


def _import_product_team_members(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "ProductTeamMembers"):
        product = _find_product(db, row)
        member = _find_team_member(db, row)
        if product is None or member is None:
            _fail(result, errors, "ProductTeamMembers", row_number, "Product and team member are required")
            continue
        assignment = db.scalar(select(ProductTeamMember).where(ProductTeamMember.product_id == product.id, ProductTeamMember.team_member_id == member.id))
        created = assignment is None
        if assignment is None:
            assignment = ProductTeamMember(product_id=product.id, team_member_id=member.id)
            db.add(assignment)
        bucket = _find_bucket(db, row, required=False)
        assignment.default_bucket_id = bucket.id if bucket else None
        assignment.status = _text(row, "status") or "active"
        result["created" if created else "updated"] += 1


def _import_product_jira_spaces(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "ProductJiraSpaces"):
        product = _find_product(db, row)
        jira_project_key = _text(row, "jira_project_key")
        if product is None or not jira_project_key:
            _fail(result, errors, "ProductJiraSpaces", row_number, "Product and Jira project key are required")
            continue
        space = db.scalar(select(ProductJiraSpace).where(ProductJiraSpace.jira_project_key == jira_project_key))
        created = space is None
        if space is None:
            space = ProductJiraSpace(product_id=product.id, jira_project_key=jira_project_key)
            db.add(space)
        space.product_id = product.id
        space.jira_project_id = _text(row, "jira_project_id")
        space.jira_project_name = _text(row, "jira_project_name")
        space.is_active = _bool(row.get("is_active"), default=True)
        space.scope_jql = _text(row, "scope_jql")
        space.validation_status = _text(row, "validation_status") or "unknown"
        space.validation_message = _text(row, "validation_message")
        result["created" if created else "updated"] += 1


def _import_jira_user_mappings(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "JiraUserMappings"):
        jira_account_id = _text(row, "jira_account_id")
        if not jira_account_id:
            _fail(result, errors, "JiraUserMappings", row_number, "Jira account id is required")
            continue
        mapping = db.scalar(select(JiraUserMapping).where(JiraUserMapping.jira_account_id == jira_account_id))
        created = mapping is None
        if mapping is None:
            mapping = JiraUserMapping(jira_account_id=jira_account_id, jira_display_name="")
            db.add(mapping)
        member = _find_team_member(db, row, required=False)
        mapping.jira_display_name = _text(row, "jira_display_name") or jira_account_id
        mapping.jira_email = _text(row, "jira_email")
        mapping.team_member_id = member.id if member else None
        result["created" if created else "updated"] += 1


def _import_jira_product_mappings(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "JiraProductMappings"):
        jira_project_key = _text(row, "jira_project_key")
        if not jira_project_key:
            _fail(result, errors, "JiraProductMappings", row_number, "Jira project key is required")
            continue
        mapping = db.scalar(select(JiraProductMapping).where(JiraProductMapping.jira_project_key == jira_project_key))
        created = mapping is None
        if mapping is None:
            mapping = JiraProductMapping(jira_project_key=jira_project_key, jira_project_name="")
            db.add(mapping)
        product = _find_product(db, row, required=False)
        mapping.jira_project_name = _text(row, "jira_project_name") or jira_project_key
        mapping.product_id = product.id if product else None
        result["created" if created else "updated"] += 1


def _import_forecast_entries(db: Session, workbook, result: dict[str, int | str], errors: list[dict[str, object]]) -> None:
    for row_number, row in _rows(workbook, "ForecastEntries"):
        product = _find_product(db, row)
        member = _find_team_member(db, row)
        bucket = _find_bucket(db, row)
        fiscal_year = _int(row, "fiscal_year")
        month_sequence = _int(row, "month_sequence")
        if product is None or member is None or bucket is None or fiscal_year is None or month_sequence is None:
            _fail(result, errors, "ForecastEntries", row_number, "Product, team member, bucket, fiscal year, and month sequence are required")
            continue
        ensure_fiscal_months(db, fiscal_year)
        month = db.scalar(select(FiscalMonth).where(FiscalMonth.fiscal_year == fiscal_year, FiscalMonth.sequence == month_sequence))
        if month is None:
            _fail(result, errors, "ForecastEntries", row_number, "Fiscal month could not be created")
            continue
        existing = db.scalar(
            select(ForecastEntry).where(
                ForecastEntry.product_id == product.id,
                ForecastEntry.team_member_id == member.id,
                ForecastEntry.bucket_id == bucket.id,
                ForecastEntry.fiscal_month_id == month.id,
            )
        )
        upsert_forecast_entry(
            db,
            product_id=product.id,
            team_member_id=member.id,
            bucket_code=bucket.code,
            fiscal_year=fiscal_year,
            month_sequence=month_sequence,
            hours=_decimal(row, "hours"),
        )
        result["updated" if existing else "created"] += 1


def _append_sheet(workbook: Workbook, sheet_name: str, headers: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> None:
    sheet = workbook.create_sheet(sheet_name)
    _append_sheet_rows(sheet, headers, rows)


def _append_sheet_rows(sheet, headers: tuple[str, ...], rows: Iterable[tuple[object, ...]]) -> None:
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    _style_sheet(sheet)


def _style_sheet(sheet) -> None:
    header_fill = PatternFill("solid", fgColor="002D72")
    header_font = Font(color="FFFFFF", bold=True)
    for cell in sheet[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="left")
    sheet.freeze_panes = "A2"
    if sheet.max_row >= 1 and sheet.max_column >= 1:
        sheet.auto_filter.ref = sheet.dimensions
    for column_cells in sheet.columns:
        values = [str(cell.value) for cell in column_cells if cell.value is not None]
        width = max([len(value) for value in values] + [12])
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(width + 2, 12), 48)


def _rows(workbook, sheet_name: str) -> Iterable[tuple[int, dict[str, object]]]:
    if sheet_name not in workbook.sheetnames:
        return []
    sheet = workbook[sheet_name]
    headers = [str(cell.value or "").strip() for cell in sheet[1]]
    row_dicts = []
    for row_number, values in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
        if all(value is None or value == "" for value in values):
            continue
        row_dicts.append((row_number, {headers[index]: value for index, value in enumerate(values) if index < len(headers)}))
    return row_dicts


def _find_product(db: Session, row: dict[str, object], required: bool = True) -> Product | None:
    name = _text(row, "product_name") or _text(row, "name")
    if name:
        product = db.scalar(select(Product).where(Product.name == name))
        if product is not None:
            return product
    product_id = _int(row, "source_product_id")
    return db.get(Product, product_id) if product_id is not None else None


def _find_team_member(db: Session, row: dict[str, object], required: bool = True) -> TeamMember | None:
    staff_id = _text(row, "staff_id")
    if staff_id:
        member = db.scalar(select(TeamMember).where(TeamMember.staff_id == staff_id))
        if member is not None:
            return member
    name = _text(row, "team_member_name") or _text(row, "name")
    if not name:
        member_id = _int(row, "source_team_member_id")
        return db.get(TeamMember, member_id) if member_id is not None else None
    member = db.scalar(select(TeamMember).where(TeamMember.name == name))
    if member is not None:
        return member
    member_id = _int(row, "source_team_member_id")
    return db.get(TeamMember, member_id) if member_id is not None else None


def _find_bucket(db: Session, row: dict[str, object], required: bool = True) -> Bucket | None:
    code = _text(row, "bucket_code") or _text(row, "code") or _text(row, "default_bucket_code")
    if code:
        bucket = db.scalar(select(Bucket).where(Bucket.code == code))
        if bucket is not None:
            return bucket
    name = _text(row, "bucket_name") or _text(row, "name") or _text(row, "default_bucket_name")
    if not name:
        bucket_id = _int(row, "source_bucket_id")
        return db.get(Bucket, bucket_id) if bucket_id is not None else None
    bucket = db.scalar(select(Bucket).where(Bucket.name == name))
    if bucket is not None:
        return bucket
    bucket_id = _int(row, "source_bucket_id")
    return db.get(Bucket, bucket_id) if bucket_id is not None else None


def _fail(result: dict[str, int | str], errors: list[dict[str, object]], sheet: str, row: int, message: str) -> None:
    result["failed"] += 1
    errors.append({"sheet": sheet, "row": row, "message": message})


def _text(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(row: dict[str, object], key: str) -> int | None:
    value = row.get(key)
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decimal(row: dict[str, object], key: str) -> Decimal:
    value = row.get(key)
    if value is None or value == "":
        return Decimal("0.00")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _bool(value: object, default: bool = False) -> bool:
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "active"}


def _number(value: Decimal | int | float | None) -> float:
    return float(value or 0)


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
