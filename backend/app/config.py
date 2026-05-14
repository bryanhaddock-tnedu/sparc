from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SPARK API"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://spark:spark@localhost:5433/spark"
    frontend_origin: str = "http://localhost:5173"
    auto_create_schema: bool = True
    seed_on_startup: bool = True
    default_fiscal_year: int = 2026

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
