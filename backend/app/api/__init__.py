from fastapi import APIRouter

from app.api import admin_data, dashboard, estimations, forecasts, integrations, products, team_members

api_router = APIRouter(prefix="/api")
api_router.include_router(admin_data.router)
api_router.include_router(dashboard.router)
api_router.include_router(products.router)
api_router.include_router(team_members.router)
api_router.include_router(forecasts.router)
api_router.include_router(integrations.router)
api_router.include_router(estimations.router)
