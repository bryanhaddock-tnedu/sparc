from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.services.access_control import (
    AuthenticatedUser,
    authenticate_local_user,
    authenticated_user_from_app_user,
    break_glass_admin,
    local_disabled_admin,
    role_capabilities,
    serialize_authenticated_user,
)
from app.services.entra_auth import entra_is_configured

AUTH_COOKIE_NAME = "sparc_session"


def auth_status(request: Request, db: Session | None = None) -> dict[str, object]:
    settings = get_settings()
    if not settings.auth_enabled:
        user = local_disabled_admin()
        return _auth_response(auth_enabled=False, authenticated=True, user=user, entra_enabled=False)

    user = current_principal(request, db)
    return _auth_response(auth_enabled=True, authenticated=user is not None, user=user, entra_enabled=entra_is_configured(settings))


def login(response: Response, username: str, password: str, db: Session | None = None) -> dict[str, object]:
    settings = get_settings()
    _require_session_configured()

    if db is not None:
        try:
            user = authenticate_local_user(db, username, password)
        except ValueError:
            user = None
        if user is not None:
            set_app_user_session(response, user.id, auth_type="app_user")
            db.commit()
            principal = authenticated_user_from_app_user(user)
            return _auth_response(auth_enabled=True, authenticated=True, user=principal)

    if _break_glass_credentials_match(username, password):
        token = _create_session_token(username, auth_type="break_glass")
        _set_session_cookie(response, token)
        return _auth_response(auth_enabled=True, authenticated=True, user=break_glass_admin(username))

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")


def logout(response: Response) -> dict[str, object]:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    settings = get_settings()
    return _auth_response(
        auth_enabled=settings.auth_enabled,
        authenticated=False,
        user=None,
        entra_enabled=entra_is_configured(settings),
    )


def require_auth(request: Request) -> None:
    if not get_settings().auth_enabled:
        return
    _require_session_configured()
    if current_username(request) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def current_user(request: Request, db: Session = Depends(get_db)) -> AuthenticatedUser:
    user = current_principal(request, db)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user


def require_admin(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def require_write_access(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
    if not role_capabilities(user.role).get("can_edit_forecast"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access required")
    return user


def require_named_people_access(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
    if not role_capabilities(user.role).get("can_view_named_people"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Named Team Member access required")
    return user


def current_principal(request: Request, db: Session | None = None) -> AuthenticatedUser | None:
    settings = get_settings()
    if not settings.auth_enabled:
        return local_disabled_admin()

    payload = current_session_payload(request)
    if payload is None:
        return None

    auth_type = str(payload.get("auth_type") or "break_glass")
    subject = payload.get("sub")
    if not subject:
        return None

    if auth_type == "app_user":
        return _current_database_user(db, subject, auth_type)
    if auth_type == "entra":
        return _current_database_user(db, subject, auth_type)

    return break_glass_admin(str(subject))


def _current_database_user(db: Session | None, subject: object, auth_type: str) -> AuthenticatedUser | None:
    if db is None:
        return None
    try:
        user_id = int(subject)
    except (TypeError, ValueError):
        return None
    from app.services.access_control import get_app_user

    user = get_app_user(db, user_id)
    if user is None or not user.is_active:
        return None
    return authenticated_user_from_app_user(user, auth_type=auth_type)


def set_app_user_session(response: Response, user_id: int, *, auth_type: str) -> None:
    token = _create_session_token(str(user_id), auth_type=auth_type)
    _set_session_cookie(response, token)


def secure_auth_cookie() -> bool:
    return _secure_cookie()


def current_username(request: Request) -> str | None:
    payload = current_session_payload(request)
    if payload is None:
        return None
    username = payload.get("sub")
    return str(username) if username else None


def current_session_payload(request: Request) -> dict[str, Any] | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    return _verify_session_token(token)


def _create_session_token(subject: str, *, auth_type: str) -> str:
    now = int(time.time())
    settings = get_settings()
    payload = {
        "sub": subject,
        "auth_type": auth_type,
        "iat": now,
        "exp": now + settings.auth_session_minutes * 60,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _sign(body)
    return f"{body}.{signature}"


def _verify_session_token(token: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(_sign(body), signature):
        return None
    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return None
    if int(payload.get("exp", 0)) < int(time.time()):
        return None
    return payload if isinstance(payload, dict) else None


def _sign(body: str) -> str:
    secret = get_settings().auth_session_secret or ""
    return hmac.new(secret.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).hexdigest()


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _constant_time_equals(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def _require_session_configured() -> None:
    settings = get_settings()
    if not settings.auth_session_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")


def _break_glass_credentials_match(username: str, password: str) -> bool:
    settings = get_settings()
    if not settings.auth_username or not settings.auth_password:
        return False
    return _constant_time_equals(username, settings.auth_username) and _constant_time_equals(password, settings.auth_password)


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=settings.auth_session_minutes * 60,
        httponly=True,
        secure=_secure_cookie(),
        samesite="lax",
        path="/",
    )


def _auth_response(
    auth_enabled: bool,
    authenticated: bool,
    user: AuthenticatedUser | None,
    *,
    entra_enabled: bool | None = None,
) -> dict[str, object]:
    username = user.email or user.display_name if user else None
    return {
        "auth_enabled": auth_enabled,
        "entra_enabled": entra_is_configured() if entra_enabled is None else entra_enabled,
        "authenticated": authenticated,
        "username": username,
        "user": serialize_authenticated_user(user) if user else None,
        "capabilities": role_capabilities(user.role) if user else {},
    }


def _secure_cookie() -> bool:
    settings = get_settings()
    return settings.frontend_origin.lower().startswith("https://")
