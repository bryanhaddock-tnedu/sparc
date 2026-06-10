from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import DashboardLaborMixResponse, DashboardSummaryResponse, DashboardWorkTypeRowResponse, ProductSummaryRowResponse
from app.services.aggregations import dashboard_labor_mix, dashboard_products, dashboard_summary, dashboard_work_type_breakdown

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(fiscal_year: int = 2027, db: Session = Depends(get_db)) -> dict[str, object]:
    return dashboard_summary(db, fiscal_year)


@router.get("/products", response_model=list[ProductSummaryRowResponse])
def get_dashboard_products(
    fiscal_year: int = 2027,
    month_sequence: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return dashboard_products(db, fiscal_year, month_sequence)


@router.get("/work-types", response_model=list[DashboardWorkTypeRowResponse])
def get_dashboard_work_types(
    fiscal_year: int = 2027,
    month_sequence: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return dashboard_work_type_breakdown(db, fiscal_year, month_sequence)


@router.get("/labor-mix", response_model=DashboardLaborMixResponse)
def get_dashboard_labor_mix(
    fiscal_year: int = 2027,
    month_sequence: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return dashboard_labor_mix(db, fiscal_year, month_sequence)
