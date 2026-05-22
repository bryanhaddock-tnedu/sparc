from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import JiraProjectCatalog, Product, ProductJiraSpace
from app.models.entities import utcnow


@dataclass(frozen=True)
class JiraProjectPayload:
    jira_project_id: str
    jira_project_key: str
    jira_project_name: str
    project_type_key: str | None = None
    is_archived: bool = False


def serialize_jira_project(project: JiraProjectCatalog) -> dict[str, object]:
    return {
        "id": project.id,
        "jira_project_id": project.jira_project_id,
        "jira_project_key": project.jira_project_key,
        "jira_project_name": project.jira_project_name,
        "project_type_key": project.project_type_key,
        "is_visible": project.is_visible,
        "is_archived": project.is_archived,
        "last_seen_at": project.last_seen_at,
        "last_checked_at": project.last_checked_at,
    }


def serialize_product_jira_space(space: ProductJiraSpace) -> dict[str, object]:
    return {
        "id": space.id,
        "product_id": space.product_id,
        "jira_project_catalog_id": space.jira_project_catalog_id,
        "jira_project_id": space.jira_project_id,
        "jira_project_key": space.jira_project_key,
        "jira_project_name": space.jira_project_name,
        "is_active": space.is_active,
        "scope_jql": space.scope_jql,
        "validation_status": space.validation_status,
        "validation_message": space.validation_message,
        "last_validated_at": space.last_validated_at,
        "created_at": space.created_at,
        "updated_at": space.updated_at,
    }


def list_jira_project_catalog(db: Session) -> list[dict[str, object]]:
    projects = db.scalars(select(JiraProjectCatalog).order_by(JiraProjectCatalog.jira_project_key)).all()
    return [serialize_jira_project(project) for project in projects]


def refresh_jira_project_catalog(db: Session) -> dict[str, object]:
    payloads = fetch_jira_projects()
    projects = [_upsert_jira_project(db, payload) for payload in payloads]
    db.flush()
    return {
        "imported": len(projects),
        "projects": [serialize_jira_project(project) for project in sorted(projects, key=lambda item: item.jira_project_key)],
    }


def list_product_jira_spaces(db: Session, product_id: int) -> list[dict[str, object]]:
    if db.get(Product, product_id) is None:
        raise ValueError("Product not found")
    spaces = db.scalars(select(ProductJiraSpace).where(ProductJiraSpace.product_id == product_id).order_by(ProductJiraSpace.jira_project_key)).all()
    return [serialize_product_jira_space(space) for space in spaces]


def add_product_jira_space(
    db: Session,
    product_id: int,
    *,
    jira_project_catalog_id: int | None = None,
    jira_project_key: str | None = None,
    is_active: bool = True,
    scope_jql: str | None = None,
) -> ProductJiraSpace:
    if db.get(Product, product_id) is None:
        raise ValueError("Product not found")

    catalog_entry = _resolve_catalog_entry(db, jira_project_catalog_id, jira_project_key)
    now = utcnow()
    space = ProductJiraSpace(
        product_id=product_id,
        jira_project_catalog_id=catalog_entry.id,
        jira_project_id=catalog_entry.jira_project_id,
        jira_project_key=catalog_entry.jira_project_key,
        jira_project_name=catalog_entry.jira_project_name,
        is_active=is_active,
        scope_jql=_clean_optional(scope_jql),
        validation_status="valid",
        validation_message="Found in Jira project catalog",
        last_validated_at=now,
    )
    db.add(space)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ValueError("Jira project is already mapped to a SPARC product") from exc
    return space


def update_product_jira_space(
    db: Session,
    product_id: int,
    space_id: int,
    updates: dict[str, object],
) -> ProductJiraSpace:
    space = _get_product_jira_space(db, product_id, space_id)
    if "is_active" in updates:
        space.is_active = bool(updates["is_active"])
    if "scope_jql" in updates:
        scope_jql = updates["scope_jql"]
        space.scope_jql = _clean_optional(str(scope_jql)) if scope_jql is not None else None
    db.flush()
    return space


def remove_product_jira_space(db: Session, product_id: int, space_id: int) -> None:
    space = _get_product_jira_space(db, product_id, space_id)
    db.delete(space)
    db.flush()


def validate_product_jira_space(db: Session, product_id: int, space_id: int) -> ProductJiraSpace:
    space = _get_product_jira_space(db, product_id, space_id)
    now = utcnow()
    catalog_entry = db.scalar(select(JiraProjectCatalog).where(JiraProjectCatalog.jira_project_key == space.jira_project_key))
    if _jira_credentials_ready():
        try:
            catalog_entry = _upsert_jira_project(db, fetch_jira_project(space.jira_project_key))
        except ValueError as exc:
            space.validation_status = "invalid"
            space.validation_message = str(exc)
            space.last_validated_at = now
            db.flush()
            return space

    if catalog_entry is None:
        space.validation_status = "invalid"
        space.validation_message = "Jira project key is not present in the local Jira catalog"
        space.last_validated_at = now
        db.flush()
        return space

    space.jira_project_catalog_id = catalog_entry.id
    space.jira_project_id = catalog_entry.jira_project_id
    space.jira_project_key = catalog_entry.jira_project_key
    space.jira_project_name = catalog_entry.jira_project_name
    space.validation_status = "valid"
    space.validation_message = "Jira project is visible to the integration account"
    space.last_validated_at = now
    db.flush()
    return space


def fetch_jira_projects() -> list[JiraProjectPayload]:
    settings = get_settings()
    _require_jira_settings(settings.jira_site_url, settings.jira_api_email, settings.jira_api_token)
    projects: list[JiraProjectPayload] = []
    start_at = 0
    max_results = 50
    with httpx.Client(timeout=30, auth=(settings.jira_api_email, settings.jira_api_token)) as client:
        while True:
            response = client.get(
                f"{settings.jira_site_url.rstrip('/')}/rest/api/3/project/search",
                params={"startAt": start_at, "maxResults": max_results},
                headers={"Accept": "application/json"},
            )
            _raise_for_jira_response(response)
            data = response.json()
            values = data.get("values", [])
            projects.extend(_project_payload_from_jira(value) for value in values)
            if data.get("isLast", False) or start_at + len(values) >= data.get("total", 0):
                break
            start_at += len(values)
            if len(values) == 0:
                break
    return projects


def fetch_jira_project(project_key: str) -> JiraProjectPayload:
    settings = get_settings()
    _require_jira_settings(settings.jira_site_url, settings.jira_api_email, settings.jira_api_token)
    key = _normalize_project_key(project_key)
    with httpx.Client(timeout=20, auth=(settings.jira_api_email, settings.jira_api_token)) as client:
        response = client.get(
            f"{settings.jira_site_url.rstrip('/')}/rest/api/3/project/{key}",
            headers={"Accept": "application/json"},
        )
        _raise_for_jira_response(response)
        return _project_payload_from_jira(response.json())


def _resolve_catalog_entry(db: Session, catalog_id: int | None, project_key: str | None) -> JiraProjectCatalog:
    catalog_entry = db.get(JiraProjectCatalog, catalog_id) if catalog_id is not None else None
    if catalog_entry is not None:
        return catalog_entry

    if not project_key:
        raise ValueError("Jira project key is required")

    key = _normalize_project_key(project_key)
    catalog_entry = db.scalar(select(JiraProjectCatalog).where(JiraProjectCatalog.jira_project_key == key))
    if catalog_entry is not None:
        return catalog_entry

    if not _jira_credentials_ready():
        raise ValueError("Jira project key was not found locally. Refresh Jira catalog or configure Jira credentials.")
    return _upsert_jira_project(db, fetch_jira_project(key))


def _upsert_jira_project(db: Session, payload: JiraProjectPayload) -> JiraProjectCatalog:
    now = utcnow()
    project = db.scalar(select(JiraProjectCatalog).where(JiraProjectCatalog.jira_project_id == payload.jira_project_id))
    if project is None:
        project = db.scalar(select(JiraProjectCatalog).where(JiraProjectCatalog.jira_project_key == payload.jira_project_key))
    if project is None:
        project = JiraProjectCatalog(
            jira_project_id=payload.jira_project_id,
            jira_project_key=payload.jira_project_key,
            jira_project_name=payload.jira_project_name,
            project_type_key=payload.project_type_key,
            is_visible=True,
            is_archived=payload.is_archived,
            last_seen_at=now,
            last_checked_at=now,
        )
        db.add(project)
    else:
        project.jira_project_id = payload.jira_project_id
        project.jira_project_key = payload.jira_project_key
        project.jira_project_name = payload.jira_project_name
        project.project_type_key = payload.project_type_key
        project.is_visible = True
        project.is_archived = payload.is_archived
        project.last_seen_at = now
        project.last_checked_at = now
    db.flush()
    return project


def _get_product_jira_space(db: Session, product_id: int, space_id: int) -> ProductJiraSpace:
    space = db.get(ProductJiraSpace, space_id)
    if space is None or space.product_id != product_id:
        raise ValueError("Product Jira project not found")
    return space


def _project_payload_from_jira(payload: dict[str, object]) -> JiraProjectPayload:
    project_id = str(payload.get("id") or "").strip()
    key = _normalize_project_key(str(payload.get("key") or ""))
    name = str(payload.get("name") or key).strip()
    if not project_id or not key:
        raise ValueError("Jira project payload is missing id or key")
    return JiraProjectPayload(
        jira_project_id=project_id,
        jira_project_key=key,
        jira_project_name=name,
        project_type_key=str(payload.get("projectTypeKey") or "") or None,
        is_archived=bool(payload.get("archived", False)),
    )


def _raise_for_jira_response(response: httpx.Response) -> None:
    if response.status_code == 404:
        raise ValueError("Jira project was not found or is not visible to the integration account")
    if response.status_code in {401, 403}:
        raise ValueError("Jira credentials are missing permission to read projects")
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ValueError(f"Jira project request failed with status {response.status_code}") from exc


def _require_jira_settings(site_url: str | None, email: str | None, token: str | None) -> None:
    if not site_url or not email or not token:
        raise ValueError("Jira credentials are not configured")


def _jira_credentials_ready() -> bool:
    settings = get_settings()
    return bool(settings.jira_site_url and settings.jira_api_email and settings.jira_api_token)


def _normalize_project_key(value: str) -> str:
    return value.strip().upper()


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
