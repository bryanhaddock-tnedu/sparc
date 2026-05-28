from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from fastapi import HTTPException, Request, Response, status

from app.config import get_settings

AUTH_COOKIE_NAME = "sparc_session"


def auth_status(request: Request) -> dict[str, object]:
    settings = get_settings()
    if not settings.auth_enabled:
        return {"auth_enabled": False, "authenticated": True, "username": None}

    username = current_username(request)
    return {"auth_enabled": True, "authenticated": username is not None, "username": username}


def login(response: Response, username: str, password: str) -> dict[str, object]:
    settings = get_settings()
    _require_auth_configured()
    if not _constant_time_equals(username, settings.auth_username or "") or not _constant_time_equals(password, settings.auth_password or ""):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = _create_session_token(username)
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=settings.auth_session_minutes * 60,
        httponly=True,
        secure=_secure_cookie(),
        samesite="lax",
        path="/",
    )
    return {"auth_enabled": True, "authenticated": True, "username": username}


def logout(response: Response) -> dict[str, object]:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"auth_enabled": get_settings().auth_enabled, "authenticated": False, "username": None}


def require_auth(request: Request) -> None:
    if not get_settings().auth_enabled:
        return
    _require_auth_configured()
    if current_username(request) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")


def current_username(request: Request) -> str | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    payload = _verify_session_token(token)
    if payload is None:
        return None
    username = payload.get("sub")
    return str(username) if username else None


def _create_session_token(username: str) -> str:
    now = int(time.time())
    settings = get_settings()
    payload = {
        "sub": username,
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


def _require_auth_configured() -> None:
    settings = get_settings()
    if not settings.auth_username or not settings.auth_password or not settings.auth_session_secret:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication is not configured")


def _secure_cookie() -> bool:
    settings = get_settings()
    return settings.frontend_origin.lower().startswith("https://")
