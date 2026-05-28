from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.services import auth


def test_login_sets_signed_cookie_and_authenticates_request(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())

    response = Response()
    result = auth.login(response, "sparc", "secret")
    cookie_value = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]

    request = Request({"type": "http", "headers": [(b"cookie", f"{auth.AUTH_COOKIE_NAME}={cookie_value}".encode("utf-8"))]})

    assert result["authenticated"] is True
    assert auth.current_username(request) == "sparc"


def test_login_rejects_invalid_password(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())

    with pytest.raises(HTTPException) as exc:
        auth.login(Response(), "sparc", "wrong")

    assert exc.value.status_code == 401


def _settings():
    return SimpleNamespace(
        auth_enabled=True,
        auth_username="sparc",
        auth_password="secret",
        auth_session_secret="test-session-secret",
        auth_session_minutes=720,
        environment="local",
        frontend_origin="http://localhost:5173",
    )
