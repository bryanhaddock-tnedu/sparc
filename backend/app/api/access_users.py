from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.errors import bad_request, conflict, not_found
from app.db.session import get_db
from app.schemas import AppUserCreate, AppUserResponse, AppUserUpdate
from app.services.access_control import create_app_user, get_app_user, list_app_users, serialize_app_user, update_app_user
from app.services.auth import require_admin

router = APIRouter(prefix="/admin/users", tags=["admin users"])


@router.get("", response_model=list[AppUserResponse])
def get_users(
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> list[dict[str, object]]:
    return [serialize_app_user(user) for user in list_app_users(db)]


@router.post("", response_model=AppUserResponse)
def create_user(
    payload: AppUserCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    try:
        user = create_app_user(
            db,
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            program_areas=payload.program_areas,
            temporary_password=payload.temporary_password,
            active=payload.active,
            local_login_enabled=payload.local_login_enabled,
        )
        db.commit()
        return serialize_app_user(user)
    except ValueError as exc:
        db.rollback()
        if "already exists" in str(exc):
            raise conflict(str(exc)) from exc
        raise bad_request(str(exc)) from exc


@router.put("/{user_id}", response_model=AppUserResponse)
def update_user(
    user_id: int,
    payload: AppUserUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> dict[str, object]:
    user = get_app_user(db, user_id)
    if user is None:
        raise not_found("SPARC user")
    try:
        user = update_app_user(
            db,
            user,
            email=payload.email,
            display_name=payload.display_name,
            role=payload.role,
            program_areas=payload.program_areas,
            active=payload.active,
            local_login_enabled=payload.local_login_enabled,
            temporary_password=payload.temporary_password,
        )
        db.commit()
        return serialize_app_user(user)
    except ValueError as exc:
        db.rollback()
        if "already exists" in str(exc):
            raise conflict(str(exc)) from exc
        raise bad_request(str(exc)) from exc
