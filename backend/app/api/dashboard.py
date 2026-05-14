from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import DashboardSummaryResponse, ProductSummaryRowResponse
from app.services.aggregations import dashboard_products, dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(fiscal_year: int = 2026, db: Session = Depends(get_db)) -> dict[str, object]:
    return dashboard_summary(db, fiscal_year)


@router.get("/products", response_model=list[ProductSummaryRowResponse])
def get_dashboard_products(fiscal_year: int = 2026, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return dashboard_products(db, fiscal_year)
