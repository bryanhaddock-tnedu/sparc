from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.errors import bad_request, conflict, not_found
from app.db.session import get_db
from app.models import ActualEntry, Bucket, ForecastEntry, Product, ProductBudget, ProductJiraSpace, ProductTeamMember, TeamMember
from app.schemas import (
    BucketDistributionResponse,
    ProductBucketTablesResponse,
    ProductCreate,
    ProductJiraSpaceCreate,
    ProductJiraSpaceResponse,
    ProductJiraSpaceUpdate,
    ProductResponse,
    ProductSummaryResponse,
    ProductTeamMemberCreate,
    ProductTeamMemberResponse,
    ProductTeamMemberUpdate,
    ProductUpdate,
)
from app.services.aggregations import bucket_distribution, product_budget_amount, product_budget_map, product_bucket_tables, product_summary, serialize_product
from app.services.jira_projects import (
    add_product_jira_space,
    list_product_jira_spaces,
    remove_product_jira_space,
    serialize_product_jira_space,
    update_product_jira_space,
    validate_product_jira_space,
)
from app.services.product_org import product_org_pair_error

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(fiscal_year: int = 2027, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    budgets = product_budget_map(db, fiscal_year)
    return [
        serialize_product(product, budgets.get(product.id, Decimal("0")))
        for product in db.scalars(select(Product).order_by(Product.name)).all()
    ]


@router.post("", response_model=ProductResponse)
def create_product(payload: ProductCreate, fiscal_year: int = 2027, db: Session = Depends(get_db)) -> dict[str, object]:
    values = payload.model_dump()
    budget_amount = values.pop("budget_amount", Decimal("0.00"))
    product = Product(**values)
    db.add(product)
    try:
        db.flush()
        upsert_product_budget(db, product.id, fiscal_year, budget_amount)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise conflict("Product name or Jira key already exists") from exc
    db.refresh(product)
    return serialize_product(product, budget_amount)


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, fiscal_year: int = 2027, db: Session = Depends(get_db)) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    return serialize_product(product, product_budget_amount(db, product_id, fiscal_year))


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(product_id: int, payload: ProductUpdate, fiscal_year: int = 2027, db: Session = Depends(get_db)) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    updates = payload.model_dump(exclude_unset=True)
    if "office" in updates or "division" in updates:
        next_office = updates.get("office", product.office)
        next_division = updates.get("division", product.division)
        if error := product_org_pair_error(next_office, next_division):
            raise bad_request(error)
    budget_amount = updates.pop("budget_amount", None)
    for key, value in updates.items():
        setattr(product, key, value)
    if budget_amount is not None:
        upsert_product_budget(db, product_id, fiscal_year, budget_amount)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise conflict("Product update conflicts with an existing record") from exc
    db.refresh(product)
    return serialize_product(product, product_budget_amount(db, product_id, fiscal_year))


@router.delete("/{product_id}", response_model=dict[str, str])
def delete_product(product_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    jira_space_count = db.scalar(
        select(func.count()).select_from(ProductJiraSpace).where(ProductJiraSpace.product_id == product_id)
    )
    if jira_space_count:
        raise conflict("Remove mapped Jira projects before deleting this product")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@router.get("/{product_id}/team-members", response_model=list[ProductTeamMemberResponse])
def list_product_team_members(product_id: int, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    assignments = db.scalars(
        select(ProductTeamMember)
        .options(
            joinedload(ProductTeamMember.team_member),
            joinedload(ProductTeamMember.default_bucket),
        )
        .where(ProductTeamMember.product_id == product_id)
        .join(ProductTeamMember.team_member)
        .order_by(TeamMember.name)
    ).all()
    return [_serialize_product_team_member(db, assignment) for assignment in assignments]


@router.post("/{product_id}/team-members", response_model=ProductTeamMemberResponse)
def add_product_team_member(
    product_id: int,
    payload: ProductTeamMemberCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    product = db.get(Product, product_id)
    if product is None:
        raise not_found("Product")
    member = db.get(TeamMember, payload.team_member_id)
    if member is None:
        raise not_found("Team member")
    if payload.default_bucket_id is not None and db.get(Bucket, payload.default_bucket_id) is None:
        raise not_found("Bucket")
    _validate_assignment_status(payload.status)
    existing = db.scalar(
        select(ProductTeamMember).where(
            ProductTeamMember.product_id == product_id,
            ProductTeamMember.team_member_id == payload.team_member_id,
        )
    )
    if existing is not None:
        raise conflict("Team member is already assigned to this product")
    assignment = ProductTeamMember(
        product_id=product_id,
        team_member_id=payload.team_member_id,
        default_bucket_id=payload.default_bucket_id,
        status=payload.status,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return _serialize_product_team_member(db, assignment)


@router.put("/{product_id}/team-members/{assignment_id}", response_model=ProductTeamMemberResponse)
def update_product_team_member(
    product_id: int,
    assignment_id: int,
    payload: ProductTeamMemberUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    assignment = db.get(ProductTeamMember, assignment_id)
    if assignment is None or assignment.product_id != product_id:
        raise not_found("Product team member")
    updates = payload.model_dump(exclude_unset=True)
    if "status" in updates:
        _validate_assignment_status(updates["status"])
    if updates.get("default_bucket_id") is not None and db.get(Bucket, updates["default_bucket_id"]) is None:
        raise not_found("Bucket")
    for key, value in updates.items():
        setattr(assignment, key, value)
    db.commit()
    db.refresh(assignment)
    return _serialize_product_team_member(db, assignment)


@router.delete("/{product_id}/team-members/{assignment_id}", response_model=dict[str, str])
def remove_product_team_member(product_id: int, assignment_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    assignment = db.get(ProductTeamMember, assignment_id)
    if assignment is None or assignment.product_id != product_id:
        raise not_found("Product team member")
    forecast_entries = db.scalars(
        select(ForecastEntry).where(
            ForecastEntry.product_id == assignment.product_id,
            ForecastEntry.team_member_id == assignment.team_member_id,
        )
    ).all()
    for entry in forecast_entries:
        db.delete(entry)
    db.delete(assignment)
    db.commit()
    return {"message": "Team member removed from product and forecast lines cleared"}


@router.get("/{product_id}/jira-spaces", response_model=list[ProductJiraSpaceResponse])
def get_product_jira_spaces(product_id: int, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    try:
        return list_product_jira_spaces(db, product_id)
    except ValueError as exc:
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.post("/{product_id}/jira-spaces", response_model=ProductJiraSpaceResponse)
def create_product_jira_space(
    product_id: int,
    payload: ProductJiraSpaceCreate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        space = add_product_jira_space(db, product_id, **payload.model_dump())
        db.commit()
        db.refresh(space)
        return serialize_product_jira_space(space)
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.put("/{product_id}/jira-spaces/{space_id}", response_model=ProductJiraSpaceResponse)
def edit_product_jira_space(
    product_id: int,
    space_id: int,
    payload: ProductJiraSpaceUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        space = update_product_jira_space(db, product_id, space_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(space)
        return serialize_product_jira_space(space)
    except ValueError as exc:
        db.rollback()
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.delete("/{product_id}/jira-spaces/{space_id}", response_model=dict[str, str])
def delete_product_jira_space(product_id: int, space_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        remove_product_jira_space(db, product_id, space_id)
        db.commit()
        return {"message": "Jira project removed from product"}
    except ValueError as exc:
        db.rollback()
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.post("/{product_id}/jira-spaces/{space_id}/validate", response_model=ProductJiraSpaceResponse)
def validate_product_jira_space_endpoint(product_id: int, space_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        space = validate_product_jira_space(db, product_id, space_id)
        db.commit()
        db.refresh(space)
        return serialize_product_jira_space(space)
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/{product_id}/summary", response_model=ProductSummaryResponse)
def get_product_summary(product_id: int, fiscal_year: int = 2027, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        return product_summary(db, product_id, fiscal_year)
    except ValueError as exc:
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.get("/{product_id}/bucket-distribution", response_model=list[BucketDistributionResponse])
def get_bucket_distribution(
    product_id: int,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return bucket_distribution(db, product_id, fiscal_year)


@router.get("/{product_id}/bucket-tables", response_model=ProductBucketTablesResponse)
def get_bucket_tables(
    product_id: int,
    fiscal_year: int = 2027,
    metric: str = "hours",
    data_type: str = "forecast",
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _ = metric, data_type
    try:
        return product_bucket_tables(db, product_id, fiscal_year)
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


def _validate_assignment_status(status: str | None) -> None:
    if status not in {"active", "inactive"}:
        raise bad_request("Product team member status must be active or inactive")


def upsert_product_budget(db: Session, product_id: int, fiscal_year: int, budget_amount: Decimal) -> ProductBudget:
    budget = db.scalar(
        select(ProductBudget).where(
            ProductBudget.product_id == product_id,
            ProductBudget.fiscal_year == fiscal_year,
        )
    )
    if budget is None:
        budget = ProductBudget(product_id=product_id, fiscal_year=fiscal_year, budget_amount=budget_amount)
        db.add(budget)
    else:
        budget.budget_amount = budget_amount
    return budget


def _serialize_product_team_member(db: Session, assignment: ProductTeamMember) -> dict[str, object]:
    forecast_count = db.scalar(
        select(func.count())
        .select_from(ForecastEntry)
        .where(
            ForecastEntry.product_id == assignment.product_id,
            ForecastEntry.team_member_id == assignment.team_member_id,
        )
    )
    actual_count = db.scalar(
        select(func.count())
        .select_from(ActualEntry)
        .where(
            ActualEntry.product_id == assignment.product_id,
            ActualEntry.team_member_id == assignment.team_member_id,
        )
    )
    member = assignment.team_member
    bucket = assignment.default_bucket
    return {
        "id": assignment.id,
        "product_id": assignment.product_id,
        "team_member_id": assignment.team_member_id,
        "team_member": member.name,
        "role": member.role,
        "team": member.team,
        "bill_rate": round(float(member.bill_rate or 0), 2),
        "employment_type": member.employment_type,
        "default_bucket_id": assignment.default_bucket_id,
        "default_bucket": bucket.name if bucket else None,
        "status": assignment.status,
        "has_forecast_entries": bool(forecast_count),
        "has_actual_entries": bool(actual_count),
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
    }
