from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas import AuthStatusResponse
from app.services.auth import auth_status, login, logout

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
