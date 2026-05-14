from fastapi import APIRouter

from app.api import dashboard, forecasts, integrations, products, team_members

api_router = APIRouter(prefix="/api")
api_router.include_router(dashboard.router)
api_router.include_router(products.router)
api_router.include_router(team_members.router)
api_router.include_router(forecasts.router)
api_router.include_router(integrations.router)
