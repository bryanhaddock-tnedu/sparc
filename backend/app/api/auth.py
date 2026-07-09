from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.schemas import AuthStatusResponse
from app.services.access_control import authenticate_entra_user
from app.services.auth import auth_status, login, logout, secure_auth_cookie, set_app_user_session
from app.services.entra_auth import (
    ENTRA_STATE_COOKIE_NAME,
    ENTRA_STATE_TTL_SECONDS,
    create_entra_state,
    entra_authorization_url,
    exchange_code_for_identity,
    verify_entra_state,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status(request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    return auth_status(request, db)


@router.post("/login", response_model=AuthStatusResponse)
def login_endpoint(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> dict[str, object]:
    return login(response, payload.username, payload.password, db)


@router.post("/logout", response_model=AuthStatusResponse)
def logout_endpoint(response: Response) -> dict[str, object]:
    return logout(response)


@router.get("/entra/login")
def entra_login() -> RedirectResponse:
    try:
        state = create_entra_state()
        redirect_url = entra_authorization_url(state)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    response = RedirectResponse(redirect_url, status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        ENTRA_STATE_COOKIE_NAME,
        state,
        max_age=ENTRA_STATE_TTL_SECONDS,
        httponly=True,
        secure=secure_auth_cookie(),
        samesite="lax",
        path="/api/auth/entra",
    )
    return response


@router.get("/entra/callback")
def entra_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Entra sign-in failed: {error}")
    if not code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entra sign-in did not return an authorization code")

    state_cookie = request.cookies.get(ENTRA_STATE_COOKIE_NAME)
    if not state or not state_cookie or state != state_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entra sign-in state could not be verified")
    try:
        if not verify_entra_state(state):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Entra sign-in state has expired")
        identity = exchange_code_for_identity(code)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    app_user = authenticate_entra_user(db, tenant_id=identity.tenant_id, object_id=identity.object_id, email=identity.email)
    if app_user is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active SPARC user is configured for this Entra identity")

    settings = get_settings()
    response = RedirectResponse(settings.frontend_origin or "/", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(ENTRA_STATE_COOKIE_NAME, path="/api/auth/entra")
    set_app_user_session(response, app_user.id, auth_type="entra")
    db.commit()
    return response
