from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import bad_request
from app.db.session import get_db
from app.schemas import (
    ForecastRecommendationDecisionRequest,
    ForecastRecommendationDecisionResponse,
    JiraProductMappingResponse,
    JiraIntegrationStatusResponse,
    JiraLiveSyncRequest,
    JiraProjectCatalogResponse,
    JiraProjectCatalogSyncResponse,
    JiraProjectCatalogUpdate,
    JiraRovoSyncResponse,
    JiraUserMapRequest,
    JiraUserMappingResponse,
    RoadmapActualRowResponse,
    RoadmapItemMapRequest,
    RoadmapItemResponse,
    RoadmapSyncResponse,
    RoadmapTicketMapRequest,
    RoadmapTicketMapResponse,
    SyncRunResponse,
)
from app.services.forecast_recommendations import create_forecast_recommendation_decision, list_forecast_recommendation_decisions
from app.services.jira_projects import list_jira_project_catalog, refresh_jira_project_catalog, update_jira_project_catalog_visibility
from app.services.jira_rovo import (
    jira_integration_status,
    list_product_mappings,
    list_sync_runs,
    list_unmapped_products,
    list_unmapped_users,
    list_user_mappings,
    map_jira_user,
    run_live_jira_rovo_sync,
    run_mock_jira_rovo_sync,
)
from app.services.roadmap import (
    DEFAULT_ROADMAP_PROJECT_KEY,
    list_roadmap_items,
    map_roadmap_ticket,
    roadmap_actual_gap_rows,
    roadmap_actual_rows,
    run_live_roadmap_sync,
    update_roadmap_item_mapping,
)
from app.services.auth import require_admin

router = APIRouter(prefix="/integrations/jira-rovo", tags=["jira-rovo"], dependencies=[Depends(require_admin)])


@router.get("/status", response_model=JiraIntegrationStatusResponse)
def get_jira_integration_status() -> dict[str, object]:
    return jira_integration_status()


@router.get("/project-catalog", response_model=list[JiraProjectCatalogResponse])
def get_jira_project_catalog(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_jira_project_catalog(db)


@router.post("/project-catalog/refresh", response_model=JiraProjectCatalogSyncResponse)
def refresh_jira_project_catalog_endpoint(db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        result = refresh_jira_project_catalog(db)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.put("/project-catalog/{project_id}", response_model=JiraProjectCatalogResponse)
def update_jira_project_catalog_endpoint(
    project_id: int,
    payload: JiraProjectCatalogUpdate,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        project = update_jira_project_catalog_visibility(db, project_id, payload.is_visible)
        db.commit()
        return project
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.post("/sync", response_model=JiraRovoSyncResponse)
def sync_mock_jira_rovo(db: Session = Depends(get_db)) -> dict[str, object]:
    result = run_mock_jira_rovo_sync(db)
    db.commit()
    return result


@router.post("/sync-live", response_model=JiraRovoSyncResponse)
def sync_live_jira_rovo(payload: JiraLiveSyncRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        result = run_live_jira_rovo_sync(db, payload.fiscal_year)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/roadmap/items", response_model=list[RoadmapItemResponse])
def get_roadmap_items(fiscal_year: int = 2027, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_roadmap_items(db, fiscal_year)


@router.put("/roadmap/items/{item_id}", response_model=RoadmapItemResponse)
def update_roadmap_item_mapping_endpoint(
    item_id: int,
    payload: RoadmapItemMapRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        result = update_roadmap_item_mapping(
            db,
            item_id,
            updates=payload.model_dump(exclude_unset=True),
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/roadmap/actuals", response_model=list[RoadmapActualRowResponse])
def get_roadmap_actuals(
    fiscal_year: int = 2027,
    month_sequence: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return roadmap_actual_rows(db, fiscal_year, month_sequence=month_sequence)


@router.get("/roadmap/actual-gaps", response_model=list[RoadmapActualRowResponse])
def get_roadmap_actual_gaps(
    fiscal_year: int = 2027,
    month_sequence: int | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return roadmap_actual_gap_rows(db, fiscal_year, month_sequence=month_sequence)


@router.get("/roadmap/forecast-recommendation-decisions", response_model=list[ForecastRecommendationDecisionResponse])
def get_forecast_recommendation_decisions(
    fiscal_year: int = 2027,
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    return list_forecast_recommendation_decisions(db, fiscal_year)


@router.post("/roadmap/forecast-recommendation-decisions", response_model=ForecastRecommendationDecisionResponse)
def create_forecast_recommendation_decision_endpoint(
    payload: ForecastRecommendationDecisionRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        result = create_forecast_recommendation_decision(
            db,
            fiscal_year=payload.fiscal_year,
            product_id=payload.product_id,
            bucket_id=payload.bucket_id,
            action=payload.action,
            target_team_member_id=payload.target_team_member_id,
            target_month_sequence=payload.target_month_sequence,
            note=payload.note,
        )
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.put("/roadmap/ticket-links/{ticket_key}", response_model=RoadmapTicketMapResponse)
def update_roadmap_ticket_mapping(
    ticket_key: str,
    payload: RoadmapTicketMapRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        result = map_roadmap_ticket(db, ticket_key, payload.roadmap_item_id)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.post("/roadmap/sync", response_model=RoadmapSyncResponse)
def sync_live_roadmap(
    fiscal_year: int = 2027,
    roadmap_project_key: str = DEFAULT_ROADMAP_PROJECT_KEY,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        result = run_live_roadmap_sync(db, fiscal_year, roadmap_project_key)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/unmapped-users", response_model=list[JiraUserMappingResponse])
def get_unmapped_users(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_unmapped_users(db)


@router.get("/unmapped-products", response_model=list[JiraProductMappingResponse])
def get_unmapped_products(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_unmapped_products(db)


@router.get("/user-mappings", response_model=list[JiraUserMappingResponse])
def get_user_mappings(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_user_mappings(db)


@router.put("/user-mappings/{mapping_id}", response_model=JiraUserMappingResponse)
def update_user_mapping(mapping_id: int, payload: JiraUserMapRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    try:
        result = map_jira_user(db, mapping_id, payload.team_member_id)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/product-mappings", response_model=list[JiraProductMappingResponse])
def get_product_mappings(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_product_mappings(db)


@router.get("/sync-runs", response_model=list[SyncRunResponse])
def get_sync_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_sync_runs(db, limit=limit)
