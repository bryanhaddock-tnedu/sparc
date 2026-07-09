from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.models import Base
from app.services import auth
from app.services.access_control import create_app_user


def test_login_sets_signed_cookie_and_authenticates_request(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())

    response = Response()
    result = auth.login(response, "sparc", "secret")
    cookie_value = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]

    request = Request({"type": "http", "headers": [(b"cookie", f"{auth.AUTH_COOKIE_NAME}={cookie_value}".encode("utf-8"))]})

    assert result["authenticated"] is True
    assert result["user"]["role"] == "ADMIN"
    assert result["capabilities"]["can_admin"] is True
    assert auth.current_username(request) == "sparc"


def test_email_user_login_returns_role_and_program_area_scope(monkeypatch):
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        create_app_user(
            db,
            email="florie@example.org",
            display_name="Florie",
            role="PROGRAM_AREA_VIEW_ONLY",
            program_areas=["Academics", "Programs"],
            temporary_password="temporary-secret",
        )
        db.commit()

        response = Response()
        result = auth.login(response, "florie@example.org", "temporary-secret", db)
        cookie_value = response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
        request = Request({"type": "http", "headers": [(b"cookie", f"{auth.AUTH_COOKIE_NAME}={cookie_value}".encode("utf-8"))]})
        status = auth.auth_status(request, db)

    assert result["authenticated"] is True
    assert result["user"]["email"] == "florie@example.org"
    assert result["user"]["role"] == "PROGRAM_AREA_VIEW_ONLY"
    assert result["user"]["program_areas"] == ["Academics", "Programs"]
    assert status["user"]["program_areas"] == ["Academics", "Programs"]
    assert status["capabilities"]["can_admin"] is False
    assert status["capabilities"]["can_view_rates"] is False
    assert status["capabilities"]["can_view_named_people"] is False


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
