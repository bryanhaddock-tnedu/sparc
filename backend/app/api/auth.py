from pydantic import BaseModel
from fastapi import APIRouter, Request, Response

from app.services.auth import auth_status, login, logout

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


@router.get("/status")
def get_auth_status(request: Request) -> dict[str, object]:
    return auth_status(request)


@router.post("/login")
def login_endpoint(payload: LoginRequest, response: Response) -> dict[str, object]:
    return login(response, payload.username, payload.password)


@router.post("/logout")
def logout_endpoint(response: Response) -> dict[str, object]:
    return logout(response)
