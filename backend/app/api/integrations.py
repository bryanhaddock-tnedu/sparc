from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import bad_request
from app.db.session import get_db
from app.schemas import (
    JiraProductMapRequest,
    JiraProductMappingResponse,
    JiraIntegrationStatusResponse,
    JiraLiveSyncRequest,
    JiraProjectCatalogResponse,
    JiraProjectCatalogSyncResponse,
    JiraProjectCatalogUpdate,
    JiraRovoSyncResponse,
    JiraUserMapRequest,
    JiraUserMappingResponse,
    SyncRunResponse,
)
from app.services.jira_projects import list_jira_project_catalog, refresh_jira_project_catalog, update_jira_project_catalog_visibility
from app.services.jira_rovo import (
    jira_integration_status,
    list_product_mappings,
    list_sync_runs,
    list_unmapped_products,
    list_unmapped_users,
    list_user_mappings,
    map_jira_product,
    map_jira_user,
    run_live_jira_rovo_sync,
    run_mock_jira_rovo_sync,
)

router = APIRouter(prefix="/integrations/jira-rovo", tags=["jira-rovo"])


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


@router.put("/product-mappings/{mapping_id}", response_model=JiraProductMappingResponse)
def update_product_mapping(
    mapping_id: int,
    payload: JiraProductMapRequest,
    db: Session = Depends(get_db),
) -> dict[str, object]:
    try:
        result = map_jira_product(db, mapping_id, payload.product_id)
        db.commit()
        return result
    except ValueError as exc:
        db.rollback()
        raise bad_request(str(exc)) from exc


@router.get("/sync-runs", response_model=list[SyncRunResponse])
def get_sync_runs(limit: int = 20, db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return list_sync_runs(db, limit=limit)
