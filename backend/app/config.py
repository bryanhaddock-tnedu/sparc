from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SPARC API"
    environment: str = "local"
    database_url: str = "postgresql+psycopg://spark:spark@localhost:5433/spark"
    frontend_origin: str = "http://localhost:5173"
    auto_create_schema: bool = True
    seed_on_startup: bool = True
    default_fiscal_year: int = 2027
    build_version: str = Field(default="local", validation_alias=AliasChoices("VITE_BUILD_VERSION", "SPARC_BUILD_VERSION", "BUILD_VERSION"))
    jira_site_url: str | None = None
    jira_api_email: str | None = None
    jira_api_token: str | None = None
    auth_enabled: bool = Field(default=False, validation_alias=AliasChoices("AUTH_ENABLED", "SPARC_AUTH_ENABLED"))
    auth_username: str | None = Field(default=None, validation_alias=AliasChoices("AUTH_USERNAME", "SPARC_AUTH_USERNAME"))
    auth_password: str | None = Field(default=None, validation_alias=AliasChoices("AUTH_PASSWORD", "SPARC_AUTH_PASSWORD"))
    auth_session_secret: str | None = Field(default=None, validation_alias=AliasChoices("AUTH_SESSION_SECRET", "SPARC_AUTH_SESSION_SECRET"))
    auth_session_minutes: int = Field(default=720, validation_alias=AliasChoices("AUTH_SESSION_MINUTES", "SPARC_AUTH_SESSION_MINUTES"))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
