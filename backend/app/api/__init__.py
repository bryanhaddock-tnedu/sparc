from fastapi import APIRouter, Depends

from app.api import access_users, admin_data, auth, dashboard, estimations, forecasts, integrations, products, reports, system_scan, team_members, teams
from app.services.auth import current_user

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)

protected_router = APIRouter(dependencies=[Depends(current_user)])
protected_router.include_router(access_users.router)
protected_router.include_router(admin_data.router)
protected_router.include_router(dashboard.router)
protected_router.include_router(products.router)
protected_router.include_router(team_members.router)
protected_router.include_router(teams.router)
protected_router.include_router(forecasts.router)
protected_router.include_router(integrations.router)
protected_router.include_router(estimations.router)
protected_router.include_router(reports.router)
protected_router.include_router(system_scan.router)
api_router.include_router(protected_router)
