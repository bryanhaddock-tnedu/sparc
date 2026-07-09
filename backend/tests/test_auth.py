from types import SimpleNamespace

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from starlette.requests import Request

from app.api import auth as auth_api
from app.models import Base
from app.services import auth
from app.services import entra_auth
from app.services.entra_auth import ENTRA_STATE_COOKIE_NAME, EntraIdentity
from app.services.access_control import authenticate_entra_user, authenticated_user_from_app_user, create_app_user


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


def test_auth_status_reports_entra_when_configured(monkeypatch):
    settings = _settings(
        entra_enabled=True,
        entra_tenant_id="tenant-id",
        entra_client_id="client-id",
        entra_client_secret="client-secret",
        entra_redirect_uri="https://sparc.uat.tnedu.gov/api/auth/entra/callback",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)

    request = Request({"type": "http", "headers": []})
    result = auth.auth_status(request)

    assert result["entra_enabled"] is True
    assert result["authenticated"] is False


def test_entra_user_login_links_existing_email():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = create_app_user(
            db,
            email="Florie@Example.ORG",
            display_name="Florie",
            role="LEADERSHIP_VIEW_ONLY",
            local_login_enabled=False,
        )
        db.commit()

        linked_user = authenticate_entra_user(db, tenant_id="tenant-id", object_id="object-id", email="florie@example.org")
        db.commit()

        assert linked_user is not None
        assert user.id == linked_user.id
        assert linked_user.entra_tenant_id == "tenant-id"
        assert linked_user.entra_object_id == "object-id"
        assert linked_user.last_login_at is not None
        principal = authenticated_user_from_app_user(linked_user, auth_type="entra")
        assert principal.auth_type == "entra"
        assert principal.email == "florie@example.org"


def test_entra_user_login_rejects_unknown_email():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = authenticate_entra_user(db, tenant_id="tenant-id", object_id="object-id", email="unknown@example.org")

    assert user is None


def test_entra_user_login_rejects_identity_conflict():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        existing_user = create_app_user(
            db,
            email="florie@example.org",
            display_name="Florie",
            role="ADMIN",
        )
        existing_user.entra_tenant_id = "tenant-id"
        existing_user.entra_object_id = "original-object-id"
        db.commit()

        user = authenticate_entra_user(db, tenant_id="tenant-id", object_id="different-object-id", email="florie@example.org")

        assert user is None
        assert existing_user.entra_object_id == "original-object-id"


def test_entra_state_rejects_tampering():
    settings = _settings(
        entra_enabled=True,
        entra_tenant_id="tenant-id",
        entra_client_id="client-id",
        entra_client_secret="client-secret",
        entra_redirect_uri="https://sparc.uat.tnedu.gov/api/auth/entra/callback",
    )

    state = entra_auth.create_entra_state(settings)
    tampered_state = f"{state}tampered"

    assert entra_auth.verify_entra_state(state, settings) is True
    assert entra_auth.verify_entra_state(tampered_state, settings) is False


def test_entra_callback_sets_session_for_existing_user(monkeypatch):
    settings = _settings(
        frontend_origin="https://sparc.uat.tnedu.gov",
        entra_enabled=True,
        entra_tenant_id="tenant-id",
        entra_client_id="client-id",
        entra_client_secret="client-secret",
        entra_redirect_uri="https://sparc.uat.tnedu.gov/api/auth/entra/callback",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(auth_api, "get_settings", lambda: settings)
    monkeypatch.setattr(entra_auth, "get_settings", lambda: settings)
    monkeypatch.setattr(
        auth_api,
        "exchange_code_for_identity",
        lambda code: EntraIdentity(tenant_id="tenant-id", object_id="object-id", email="florie@example.org", display_name="Florie"),
    )
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        create_app_user(
            db,
            email="florie@example.org",
            display_name="Florie",
            role="ADMIN",
            local_login_enabled=False,
        )
        db.commit()

        state = entra_auth.create_entra_state(settings)
        request = Request({"type": "http", "headers": [(b"cookie", f"{ENTRA_STATE_COOKIE_NAME}={state}".encode("utf-8"))]})
        response = auth_api.entra_callback(request, code="auth-code", state=state, db=db)
        set_cookie_headers = [
            value.decode("utf-8")
            for key, value in response.raw_headers
            if key.decode("ascii").lower() == "set-cookie"
        ]

        assert response.status_code == 303
        assert response.headers["location"] == "https://sparc.uat.tnedu.gov"
        assert any(cookie.startswith(f"{auth.AUTH_COOKIE_NAME}=") for cookie in set_cookie_headers)
        user = authenticate_entra_user(db, tenant_id="tenant-id", object_id="object-id", email=None)
        assert user is not None
        assert user.email == "florie@example.org"


def _settings(**overrides):
    values = {
        "auth_enabled": True,
        "auth_username": "sparc",
        "auth_password": "secret",
        "auth_session_secret": "test-session-secret",
        "auth_session_minutes": 720,
        "environment": "local",
        "frontend_origin": "http://localhost:5173",
        "entra_enabled": False,
        "entra_tenant_id": None,
        "entra_client_id": None,
        "entra_client_secret": None,
        "entra_redirect_uri": None,
        "entra_authority_url": None,
        "entra_post_logout_redirect_uri": None,
    }
    values.update(overrides)
    return SimpleNamespace(
        **values,
    )
