from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.errors import bad_request, conflict, not_found
from app.db.session import get_db
from app.models import Product
from app.schemas import (
    BucketDistributionResponse,
    ProductBucketTablesResponse,
    ProductCreate,
    ProductResponse,
    ProductSummaryResponse,
    ProductUpdate,
)
from app.services.aggregations import bucket_distribution, product_bucket_tables, product_summary, serialize_product

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [serialize_product(product) for product in db.scalars(select(Product).order_by(Product.name)).all()]


@router.post("", response_model=ProductResponse)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)) -> dict[str, object]:
    product = Product(**payload.model_dump())
    db.add(product)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise conflict("Product name or Jira space key already exists") from exc
    db.refresh(product)
    return serialize_product(product)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    return serialize_product(product)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, db: Session = Depends(get_db)) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise conflict("Product update conflicts with an existing record") from exc
    db.refresh(product)
    return serialize_product(product)


@router.get("/{product_id}/summary", response_model=ProductSummaryResponse)
def get_product_summary(product_id: int, fiscal_year: int = 2026, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return product_summary(db, product_id, fiscal_year)
    except ValueError as exc:
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.get("/{product_id}/bucket-distribution", response_model=list[BucketDistributionResponse])
def get_bucket_distribution(
    product_id: int,
    fiscal_year: int = 2026,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return bucket_distribution(db, product_id, fiscal_year)


@router.get("/{product_id}/bucket-tables", response_model=ProductBucketTablesResponse)
def get_bucket_tables(
    product_id: int,
    fiscal_year: int = 2026,
    metric: str = "hours",
    data_type: str = "forecast",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _ = metric, data_type
    try:
        return product_bucket_tables(db, product_id, fiscal_year)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc
