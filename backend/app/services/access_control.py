from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
import hashlib
import hmac
import secrets

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import AppUser, UserProgramAreaAssignment
from app.services.product_org import PRODUCT_OFFICES, clean_product_org_value


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    LEADERSHIP_VIEW_ONLY = "LEADERSHIP_VIEW_ONLY"
    PROGRAM_AREA_VIEW_ONLY = "PROGRAM_AREA_VIEW_ONLY"


ROLE_LABELS = {
    UserRole.ADMIN: "Admin",
    UserRole.LEADERSHIP_VIEW_ONLY: "Leadership View Only",
    UserRole.PROGRAM_AREA_VIEW_ONLY: "Program Area View Only",
}

PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
PASSWORD_HASH_ITERATIONS = 260_000


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int | None
    email: str | None
    display_name: str
    role: UserRole
    program_areas: tuple[str, ...] = ()
    auth_type: str = "local"
    active: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN


def role_capabilities(role: UserRole) -> dict[str, bool]:
    if role == UserRole.ADMIN:
        return {
            "can_admin": True,
            "can_edit_forecast": True,
            "can_run_sync": True,
            "can_view_rates": True,
            "can_view_costs": True,
            "can_view_hours": True,
            "can_view_work_type_breakdown": True,
            "can_view_named_people": True,
            "can_view_labor_details": True,
            "can_view_team_member_profiles": True,
            "can_view_team_pages": True,
            "can_view_reports": True,
        }
    if role == UserRole.LEADERSHIP_VIEW_ONLY:
        return {
            "can_admin": False,
            "can_edit_forecast": False,
            "can_run_sync": False,
            "can_view_rates": False,
            "can_view_costs": True,
            "can_view_hours": True,
            "can_view_work_type_breakdown": True,
            "can_view_named_people": True,
            "can_view_labor_details": False,
            "can_view_team_member_profiles": False,
            "can_view_team_pages": False,
            "can_view_reports": True,
        }
    return {
        "can_admin": False,
        "can_edit_forecast": False,
        "can_run_sync": False,
        "can_view_rates": False,
        "can_view_costs": True,
        "can_view_hours": False,
        "can_view_work_type_breakdown": True,
        "can_view_named_people": False,
        "can_view_labor_details": False,
        "can_view_team_member_profiles": False,
        "can_view_team_pages": False,
        "can_view_reports": False,
    }


def serialize_authenticated_user(user: AuthenticatedUser) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role.value,
        "role_label": ROLE_LABELS[user.role],
        "program_areas": list(user.program_areas),
        "auth_type": user.auth_type,
        "active": user.active,
    }


def scoped_program_areas(user: AuthenticatedUser) -> tuple[str, ...] | None:
    if user.role in {UserRole.ADMIN, UserRole.LEADERSHIP_VIEW_ONLY}:
        return None
    return user.program_areas


def can_view_product_office(user: AuthenticatedUser, office: str | None) -> bool:
    allowed_program_areas = scoped_program_areas(user)
    if allowed_program_areas is None:
        return True
    if office is None:
        return False
    return office in allowed_program_areas


def serialize_app_user(user: AppUser) -> dict[str, object]:
    program_areas = sorted(assignment.program_area for assignment in user.program_area_assignments)
    role = normalize_role(user.role)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": role.value,
        "role_label": ROLE_LABELS[role],
        "program_areas": program_areas,
        "active": user.is_active,
        "local_login_enabled": user.local_login_enabled,
        "has_local_password": bool(user.password_hash),
        "entra_tenant_id": user.entra_tenant_id,
        "entra_object_id": user.entra_object_id,
        "sso_linked": bool(user.entra_tenant_id and user.entra_object_id),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def list_app_users(db: Session) -> list[AppUser]:
    return list(
        db.scalars(
            select(AppUser)
            .options(selectinload(AppUser.program_area_assignments))
            .order_by(func.lower(AppUser.display_name), func.lower(AppUser.email))
        )
    )


def get_app_user(db: Session, user_id: int) -> AppUser | None:
    return db.scalar(
        select(AppUser)
        .options(selectinload(AppUser.program_area_assignments))
        .where(AppUser.id == user_id)
    )


def get_app_user_by_email(db: Session, email: str) -> AppUser | None:
    normalized_email = normalize_email(email)
    return db.scalar(
        select(AppUser)
        .options(selectinload(AppUser.program_area_assignments))
        .where(func.lower(AppUser.email) == normalized_email.lower())
    )


def get_app_user_by_entra_identity(db: Session, tenant_id: str, object_id: str) -> AppUser | None:
    tenant = str(tenant_id or "").strip()
    oid = str(object_id or "").strip()
    if not tenant or not oid:
        return None
    return db.scalar(
        select(AppUser)
        .options(selectinload(AppUser.program_area_assignments))
        .where(AppUser.entra_tenant_id == tenant, AppUser.entra_object_id == oid)
    )


def create_app_user(
    db: Session,
    *,
    email: str,
    display_name: str,
    role: str,
    program_areas: list[str] | None = None,
    temporary_password: str | None = None,
    active: bool = True,
    local_login_enabled: bool = True,
) -> AppUser:
    normalized_email = normalize_email(email)
    if db.scalar(select(AppUser).where(func.lower(AppUser.email) == normalized_email.lower())) is not None:
        raise ValueError("A SPARC user with this email already exists")

    user = AppUser(
        email=normalized_email,
        display_name=clean_display_name(display_name, normalized_email),
        role=normalize_role(role).value,
        is_active=active,
        local_login_enabled=local_login_enabled,
        password_hash=hash_password(temporary_password) if temporary_password else None,
    )
    db.add(user)
    db.flush()
    replace_program_area_assignments(
        db,
        user,
        program_areas_for_role(normalize_role(user.role), program_areas or []),
    )
    db.flush()
    return get_app_user(db, user.id) or user


def update_app_user(
    db: Session,
    user: AppUser,
    *,
    email: str | None = None,
    display_name: str | None = None,
    role: str | None = None,
    program_areas: list[str] | None = None,
    active: bool | None = None,
    local_login_enabled: bool | None = None,
    temporary_password: str | None = None,
) -> AppUser:
    if email is not None:
        normalized_email = normalize_email(email)
        existing = db.scalar(select(AppUser).where(func.lower(AppUser.email) == normalized_email.lower(), AppUser.id != user.id))
        if existing is not None:
            raise ValueError("A SPARC user with this email already exists")
        user.email = normalized_email
    if display_name is not None:
        user.display_name = clean_display_name(display_name, user.email)
    if role is not None:
        user.role = normalize_role(role).value
    if active is not None:
        user.is_active = active
    if local_login_enabled is not None:
        user.local_login_enabled = local_login_enabled
    if temporary_password is not None:
        user.password_hash = hash_password(temporary_password) if temporary_password else None
    if program_areas is not None:
        replace_program_area_assignments(
            db,
            user,
            program_areas_for_role(normalize_role(user.role), program_areas),
        )
    elif role is not None and normalize_role(user.role) != UserRole.PROGRAM_AREA_VIEW_ONLY:
        replace_program_area_assignments(db, user, [])
    db.flush()
    return get_app_user(db, user.id) or user


def replace_program_area_assignments(db: Session, user: AppUser, program_areas: list[str]) -> None:
    normalized = normalize_program_areas(program_areas)
    requested = set(normalized)
    existing = {assignment.program_area: assignment for assignment in user.program_area_assignments}

    for program_area, assignment in existing.items():
        if program_area not in requested:
            user.program_area_assignments.remove(assignment)
    for program_area in normalized:
        if program_area in existing:
            continue
        user.program_area_assignments.append(UserProgramAreaAssignment(program_area=program_area))
    db.flush()


def program_areas_for_role(role: UserRole, program_areas: list[str]) -> list[str]:
    if role != UserRole.PROGRAM_AREA_VIEW_ONLY:
        return []
    return program_areas


def authenticate_local_user(db: Session, identifier: str, password: str) -> AppUser | None:
    email = normalize_email(identifier)
    user = db.scalar(
        select(AppUser)
        .options(selectinload(AppUser.program_area_assignments))
        .where(func.lower(AppUser.email) == email.lower())
    )
    if user is None or not user.is_active or not user.local_login_enabled or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def authenticate_entra_user(
    db: Session,
    *,
    tenant_id: str,
    object_id: str,
    email: str | None,
) -> AppUser | None:
    tenant = str(tenant_id or "").strip()
    oid = str(object_id or "").strip()
    if not tenant or not oid:
        return None

    user = get_app_user_by_entra_identity(db, tenant, oid)
    if user is None and email:
        try:
            user = get_app_user_by_email(db, email)
        except ValueError:
            user = None
        if user is not None:
            if (user.entra_tenant_id or user.entra_object_id) and (user.entra_tenant_id != tenant or user.entra_object_id != oid):
                return None
            user.entra_tenant_id = tenant
            user.entra_object_id = oid

    if user is None or not user.is_active:
        return None

    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def authenticated_user_from_app_user(user: AppUser, *, auth_type: str = "local") -> AuthenticatedUser:
    return AuthenticatedUser(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=normalize_role(user.role),
        program_areas=tuple(sorted(assignment.program_area for assignment in user.program_area_assignments)),
        auth_type=auth_type,
        active=user.is_active,
    )


def break_glass_admin(username: str | None = None) -> AuthenticatedUser:
    display_name = username or "sparc"
    return AuthenticatedUser(
        id=None,
        email=None,
        display_name=display_name,
        role=UserRole.ADMIN,
        program_areas=(),
        auth_type="break_glass",
        active=True,
    )


def local_disabled_admin() -> AuthenticatedUser:
    return AuthenticatedUser(
        id=None,
        email=None,
        display_name="Local Admin",
        role=UserRole.ADMIN,
        program_areas=(),
        auth_type="disabled_auth",
        active=True,
    )


def normalize_role(value: str | UserRole) -> UserRole:
    if isinstance(value, UserRole):
        return value
    normalized = str(value or "").strip().upper()
    aliases = {
        "ADMIN": UserRole.ADMIN,
        "LEADERSHIP": UserRole.LEADERSHIP_VIEW_ONLY,
        "LEADERSHIP_VIEW_ONLY": UserRole.LEADERSHIP_VIEW_ONLY,
        "PROGRAM_AREA": UserRole.PROGRAM_AREA_VIEW_ONLY,
        "PROGRAM_AREA_VIEW": UserRole.PROGRAM_AREA_VIEW_ONLY,
        "PROGRAM_AREA_VIEW_ONLY": UserRole.PROGRAM_AREA_VIEW_ONLY,
    }
    if normalized not in aliases:
        raise ValueError("Role must be Admin, Leadership View Only, or Program Area View Only")
    return aliases[normalized]


def normalize_email(value: str) -> str:
    email = str(value or "").strip().lower()
    if not email or "@" not in email:
        raise ValueError("Email address is required")
    return email


def clean_display_name(value: str | None, fallback_email: str) -> str:
    name = str(value or "").strip()
    return name or fallback_email


def normalize_program_areas(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_value in values:
        value = clean_product_org_value(raw_value)
        if value is None:
            continue
        if value not in PRODUCT_OFFICES:
            raise ValueError(f"Program Area must be one of: {', '.join(PRODUCT_OFFICES)}")
        if value not in normalized:
            normalized.append(value)
    return normalized


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password is required")
    salt = secrets.token_urlsafe(18)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_HASH_ITERATIONS)
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{PASSWORD_HASH_ALGORITHM}${PASSWORD_HASH_ITERATIONS}${salt}${encoded_digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations_text, salt, expected_digest = password_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if algorithm != PASSWORD_HASH_ALGORITHM:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(encoded_digest, expected_digest)
