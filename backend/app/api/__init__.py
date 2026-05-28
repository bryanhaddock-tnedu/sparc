from fastapi import APIRouter, Depends

from app.api import admin_data, auth, dashboard, estimations, forecasts, integrations, products, team_members
from app.services.auth import require_auth

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)

protected_router = APIRouter(dependencies=[Depends(require_auth)])
protected_router.include_router(admin_data.router)
protected_router.include_router(dashboard.router)
protected_router.include_router(products.router)
protected_router.include_router(team_members.router)
protected_router.include_router(forecasts.router)
protected_router.include_router(integrations.router)
protected_router.include_router(estimations.router)
api_router.include_router(protected_router)
