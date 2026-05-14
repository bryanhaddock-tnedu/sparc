from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api import api_router
from app.config import get_settings
from app.db.seed import seed_database
from app.db.session import SessionLocal, create_database

settings = get_settings()
logger = logging.getLogger("spark")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ = app
    if settings.auto_create_schema:
        create_database()
    if settings.seed_on_startup:
        with SessionLocal() as db:
            seed_database(db)
    logger.info(
        "SPARK startup complete environment=%s auto_create_schema=%s seed_on_startup=%s",
        settings.environment,
        settings.auto_create_schema,
        settings.seed_on_startup,
    )
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready")
def readiness() -> dict[str, str]:
    try:
        with SessionLocal() as db:
            db.execute(text("select 1"))
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail={"status": "not_ready"})
    return {"status": "ready"}


app.include_router(api_router)
