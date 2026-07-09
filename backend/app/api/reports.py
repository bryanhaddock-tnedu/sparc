from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.errors import bad_request
from app.db.session import get_db
from app.services.reporting import build_labor_cost_report, build_labor_cost_report_workbook, normalize_labor_cost_dimensions
from app.services.access_control import AuthenticatedUser
from app.services.auth import current_user

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/labor-cost")
def get_labor_cost_report(
    fiscal_year: int = 2027,
    lead: str = Query(default="person"),
    second: str | None = Query(default="product"),
    third: str | None = Query(default="bucket"),
    sort: str = Query(default="forecast_cost"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    try:
        dimensions = normalize_labor_cost_dimensions(lead, second, third)
        return build_labor_cost_report(db, fiscal_year, dimensions=dimensions, sort_metric=sort, user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


@router.get("/labor-cost.xlsx")
def export_labor_cost_report(
    fiscal_year: int = 2027,
    lead: str = Query(default="person"),
    second: str | None = Query(default="product"),
    third: str | None = Query(default="bucket"),
    sort: str = Query(default="forecast_cost"),
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(current_user),
) -> StreamingResponse:
    try:
        dimensions = normalize_labor_cost_dimensions(lead, second, third)
        workbook = build_labor_cost_report_workbook(db, fiscal_year, dimensions=dimensions, sort_metric=sort, user=user)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
    filename = f"labor-cost-report-{datetime.now(timezone.utc).strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
