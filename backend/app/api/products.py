from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.api.errors import bad_request, conflict, not_found
from app.db.session import get_db
from app.models import (
    ActualEntry,
    Bucket,
    EstimatedEntry,
    EstimatedIssueAllocation,
    ForecastEntry,
    ForecastRecommendationDecision,
    JiraProductMapping,
    Product,
    ProductBudget,
    ProductJiraSpace,
    ProductTeamMember,
    RoadmapItem,
    RoadmapItemIssueLink,
    TeamMember,
)
from app.schemas import (
    BucketDistributionResponse,
    BucketResponse,
    ProductBucketTablesResponse,
    ProductCreate,
    ProductJiraSpaceCreate,
    ProductJiraSpaceMoveRequest,
    ProductJiraSpaceMoveResponse,
    ProductJiraSpaceResponse,
    ProductJiraSpaceUpdate,
    ProductResponse,
    ProductRoleBreakdownResponse,
    TicketCostReceiptResponse,
    RoadmapActualRowResponse,
    RoadmapItemResponse,
    ProductSummaryResponse,
    ProductTeamMemberCreate,
    ProductTeamMemberResponse,
    ProductTeamMemberUpdate,
    ProductUpdate,
)
from app.services.aggregations import bucket_distribution, product_budget_amount, product_budget_map, product_bucket_tables, product_role_breakdown, product_summary, serialize_product
from app.services.access_control import AuthenticatedUser, can_view_product_office, role_capabilities
from app.services.auth import (
    current_user,
    require_admin,
    require_labor_detail_access,
    require_role_breakdown_access,
    require_ticket_cost_receipt_access,
    require_work_type_breakdown_access,
)
from app.services.jira_projects import (
    add_product_jira_space,
    list_product_jira_spaces,
    move_product_jira_space,
    remove_product_jira_space,
    serialize_product_jira_space,
    update_product_jira_space,
    validate_product_jira_space,
)
from app.services.product_org import product_org_pair_error
from app.services.roadmap import product_roadmap_items, roadmap_actual_rows
from app.services.ticket_cost_receipts import product_ticket_cost_receipts
from app.services.slugs import resolve_product_ref, team_member_url_slug, unique_product_slug

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductResponse])
def list_products(
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(current_user),
) -> list[dict[str, object]]:
    budgets = product_budget_map(db, fiscal_year)
    return [
        serialize_product(product, budgets.get(product.id, Decimal("0")))
        for product in db.scalars(select(Product).order_by(Product.name)).all()
        if can_view_product_office(user, product.office)
    ]


@router.post("", response_model=ProductResponse)
def create_product(
    payload: ProductCreate,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    values = payload.model_dump()
    budget_amount = values.pop("budget_amount", Decimal("0.00"))
    product = Product(**values)
    product.slug = unique_product_slug(db, product.name)
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


@router.get("/buckets", response_model=list[BucketResponse])
def list_buckets(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [
        {"id": bucket.id, "code": bucket.code, "name": bucket.name}
        for bucket in db.scalars(select(Bucket).order_by(Bucket.id)).all()
    ]


@router.get("/{product_ref}", response_model=ProductResponse)
def get_product(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    product_id = product.id
    if product.slug is None:
        product.slug = unique_product_slug(db, product.name, product.id)
        db.commit()
        db.refresh(product)
    return serialize_product(product, product_budget_amount(db, product_id, fiscal_year))


@router.put("/{product_ref}", response_model=ProductResponse)
def update_product(
    product_ref: str,
    payload: ProductUpdate,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    product_id = product.id
    updates = payload.model_dump(exclude_unset=True)
    if "office" in updates or "division" in updates:
        next_office = updates.get("office", product.office)
        next_division = updates.get("division", product.division)
        if error := product_org_pair_error(next_office, next_division):
            raise bad_request(error)
    budget_amount = updates.pop("budget_amount", None)
    if "name" in updates and updates["name"] != product.name:
        product.slug = unique_product_slug(db, updates["name"], product.id)
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


@router.delete("/{product_ref}", response_model=dict[str, str])
def delete_product(product_ref: str, db: Session = Depends(get_db), _admin=Depends(require_admin)) -> dict[str, str]:
    product = _resolve_product_or_404(db, product_ref)
    product_id = product.id
    protected_references = (
        ("mapped Jira projects", ProductJiraSpace),
        ("forecast entries", ForecastEntry),
        ("actual entries", ActualEntry),
        ("estimated entries", EstimatedEntry),
        ("estimated issue allocations", EstimatedIssueAllocation),
        ("forecast recommendation decisions", ForecastRecommendationDecision),
        ("Roadmap Items", RoadmapItem),
        ("Roadmap issue links", RoadmapItemIssueLink),
        ("legacy Jira references", JiraProductMapping),
    )
    for label, model in protected_references:
        reference_count = db.scalar(select(func.count()).select_from(model).where(model.product_id == product_id))
        if reference_count:
            raise conflict(f"Product has {label}. Mark it inactive instead of deleting it so history is retained.")
    db.delete(product)
    db.commit()
    return {"message": "Product deleted"}


@router.get("/{product_ref}/team-members", response_model=list[ProductTeamMemberResponse])
def list_product_team_members(
    product_ref: str,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_labor_detail_access),
) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    product_id = product.id
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
    return [_serialize_product_team_member(db, assignment, can_view_rates=_can_view_rates(user)) for assignment in assignments]


@router.post("/{product_ref}/team-members", response_model=ProductTeamMemberResponse)
def add_product_team_member(
    product_ref: str,
    payload: ProductTeamMemberCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    product_id = product.id
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


@router.put("/{product_ref}/team-members/{assignment_id}", response_model=ProductTeamMemberResponse)
def update_product_team_member(
    product_ref: str,
    assignment_id: int,
    payload: ProductTeamMemberUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    product_id = product.id
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


@router.delete("/{product_ref}/team-members/{assignment_id}", response_model=dict[str, str])
def remove_product_team_member(
    product_ref: str,
    assignment_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, str]:
    product = _resolve_product_or_404(db, product_ref)
    product_id = product.id
    assignment = db.get(ProductTeamMember, assignment_id)
    if assignment is None or assignment.product_id != product_id:
        raise not_found("Product team member")
    historical_models = (ForecastEntry, ActualEntry, EstimatedEntry, EstimatedIssueAllocation)
    has_labor_history = any(
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(model.product_id == assignment.product_id, model.team_member_id == assignment.team_member_id)
        )
        for model in historical_models
    )
    if has_labor_history:
        assignment.status = "inactive"
        assignment.default_bucket_id = None
        db.commit()
        return {"message": "Team member marked inactive; forecast and labor history retained"}
    db.delete(assignment)
    db.commit()
    return {"message": "Team member removed from product"}


@router.get("/{product_ref}/jira-spaces", response_model=list[ProductJiraSpaceResponse])
def get_product_jira_spaces(product_ref: str, db: Session = Depends(get_db), _admin=Depends(require_admin)) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    try:
        return list_product_jira_spaces(db, product.id)
    except ValueError as exc:
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.post("/{product_ref}/jira-spaces", response_model=ProductJiraSpaceResponse)
def create_product_jira_space(
    product_ref: str,
    payload: ProductJiraSpaceCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    try:
        space = add_product_jira_space(db, product.id, **payload.model_dump())
        db.commit()
        db.refresh(space)
        return serialize_product_jira_space(space)
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.put("/{product_ref}/jira-spaces/{space_id}", response_model=ProductJiraSpaceResponse)
def edit_product_jira_space(
    product_ref: str,
    space_id: int,
    payload: ProductJiraSpaceUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    try:
        space = update_product_jira_space(db, product.id, space_id, payload.model_dump(exclude_unset=True))
        db.commit()
        db.refresh(space)
        return serialize_product_jira_space(space)
    except ValueError as exc:
        db.rollback()
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.post("/{product_ref}/jira-spaces/{space_id}/move", response_model=ProductJiraSpaceMoveResponse)
def move_product_jira_space_endpoint(
    product_ref: str,
    space_id: int,
    payload: ProductJiraSpaceMoveRequest,
    db: Session = Depends(get_db),
    admin: AuthenticatedUser = Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    try:
        result = move_product_jira_space(
            db,
            product.id,
            space_id,
            payload.target_product_id,
            actor=admin,
            reason=payload.reason,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.delete("/{product_ref}/jira-spaces/{space_id}", response_model=dict[str, str])
def delete_product_jira_space(
    product_ref: str,
    space_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, str]:
    product = _resolve_product_or_404(db, product_ref)
    try:
        remove_product_jira_space(db, product.id, space_id)
        db.commit()
        return {"message": "Jira project removed from product"}
    except ValueError as exc:
        db.rollback()
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.post("/{product_ref}/jira-spaces/{space_id}/validate", response_model=ProductJiraSpaceResponse)
def validate_product_jira_space_endpoint(
    product_ref: str,
    space_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    try:
        space = validate_product_jira_space(db, product.id, space_id)
        db.commit()
        db.refresh(space)
        return serialize_product_jira_space(space)
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/{product_ref}/summary", response_model=ProductSummaryResponse)
def get_product_summary(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(current_user),
) -> dict[str, object]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    try:
        return product_summary(db, product.id, fiscal_year, user=user)
    except ValueError as exc:
        raise not_found(str(exc).replace(" not found", "")) from exc


@router.get("/{product_ref}/bucket-distribution", response_model=list[BucketDistributionResponse])
def get_bucket_distribution(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_work_type_breakdown_access),
) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    return bucket_distribution(db, product.id, fiscal_year)


@router.get("/{product_ref}/role-breakdown", response_model=list[ProductRoleBreakdownResponse])
def get_product_role_breakdown(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_role_breakdown_access),
) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    return product_role_breakdown(db, product.id, fiscal_year)


@router.get("/{product_ref}/ticket-cost-receipts", response_model=list[TicketCostReceiptResponse])
def get_product_ticket_cost_receipts(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_ticket_cost_receipt_access),
) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    return product_ticket_cost_receipts(db, product.id, fiscal_year)


@router.get("/{product_ref}/bucket-tables", response_model=ProductBucketTablesResponse)
def get_bucket_tables(
    product_ref: str,
    fiscal_year: int = 2027,
    metric: str = "hours",
    data_type: str = "forecast",
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_labor_detail_access),
) -> dict[str, object]:
    _ = metric, data_type
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    try:
        return product_bucket_tables(db, product.id, fiscal_year, can_view_rates=_can_view_rates(user))
    except ValueError as exc:
        raise bad_request(str(exc)) from exc


@router.get("/{product_ref}/roadmap-actuals", response_model=list[RoadmapActualRowResponse])
def get_product_roadmap_actuals(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(require_labor_detail_access),
) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    return roadmap_actual_rows(db, fiscal_year, product_id=product.id)


@router.get("/{product_ref}/roadmap-items", response_model=list[RoadmapItemResponse])
def get_product_roadmap_items(
    product_ref: str,
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
    user: AuthenticatedUser = Depends(current_user),
) -> list[dict[str, object]]:
    product = _resolve_product_or_404(db, product_ref)
    _require_product_visible(product, user)
    return product_roadmap_items(db, product.id, fiscal_year)


def _resolve_product_or_404(db: Session, product_ref: str) -> Product:
    product = resolve_product_ref(db, product_ref)
    if product is None:
        raise not_found("Product")
    return product


def _require_product_visible(product: Product, user: AuthenticatedUser) -> None:
    if not can_view_product_office(user, product.office):
        raise not_found("Product")


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


def _can_view_rates(user: AuthenticatedUser) -> bool:
    return role_capabilities(user.role).get("can_view_rates", False)


def _serialize_product_team_member(db: Session, assignment: ProductTeamMember, *, can_view_rates: bool = True) -> dict[str, object]:
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
        "team_member_slug": team_member_url_slug(member),
        "role": member.role,
        "team": member.team,
        "bill_rate": round(float(member.bill_rate or 0), 2) if can_view_rates else None,
        "employment_type": member.employment_type,
        "default_bucket_id": assignment.default_bucket_id,
        "default_bucket": bucket.name if bucket else None,
        "status": assignment.status,
        "has_forecast_entries": bool(forecast_count),
        "has_actual_entries": bool(actual_count),
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
    }
