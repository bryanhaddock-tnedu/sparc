from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import SystemScanResponse
from app.services.system_scan import run_system_scan

router = APIRouter(prefix="/system-scan", tags=["system scan"])


@router.get("", response_model=SystemScanResponse)
def get_system_scan(
    fiscal_year: int = 2027,
    budget_warning_percent: float = Query(default=85.0, ge=0, le=200),
    member_forecast_limit_hours: float = Query(default=10.0, ge=0, le=500),
    working_days: int = Query(default=7, ge=1, le=30),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return run_system_scan(
        db,
        fiscal_year,
        budget_warning_percent=budget_warning_percent,
        member_forecast_limit_hours=member_forecast_limit_hours,
        working_days=working_days,
    )
