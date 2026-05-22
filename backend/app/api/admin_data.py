from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.errors import bad_request
from app.db.session import get_db
from app.schemas import AdminDataExportOptionResponse, AdminDataImportResult
from app.services.admin_data import build_admin_data_archive, build_admin_data_export, export_options, import_admin_data_content, normalize_dataset_keys

router = APIRouter(prefix="/admin-data", tags=["admin data"])


@router.get("/export-options", response_model=list[AdminDataExportOptionResponse])
def get_admin_data_export_options() -> list[dict[str, object]]:
    return export_options()


@router.get("/export")
def export_admin_data(
    datasets: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        selected = normalize_dataset_keys(datasets)
        archive = build_admin_data_archive(db, selected)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    filename = f"sparc-admin-data-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export.xlsx")
def export_admin_data_workbook(
    datasets: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    try:
        selected = normalize_dataset_keys(datasets)
        workbook = build_admin_data_export(db, selected)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    filename = f"sparc-admin-data-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/import", response_model=AdminDataImportResult)
async def import_admin_data(
    file: UploadFile,
    datasets: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        selected = normalize_dataset_keys(datasets)
        result = import_admin_data_content(db, await file.read(), file.filename, selected)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc
    except Exception:
        db.rollback()
        raise
