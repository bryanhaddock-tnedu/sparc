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
    jira_auto_sync_enabled: bool = Field(default=True, validation_alias=AliasChoices("JIRA_AUTO_SYNC_ENABLED", "SPARC_JIRA_AUTO_SYNC_ENABLED"))
    jira_auto_sync_time: str = Field(default="07:30", validation_alias=AliasChoices("JIRA_AUTO_SYNC_TIME", "SPARC_JIRA_AUTO_SYNC_TIME"))
    jira_auto_sync_timezone: str = Field(default="America/Chicago", validation_alias=AliasChoices("JIRA_AUTO_SYNC_TIMEZONE", "SPARC_JIRA_AUTO_SYNC_TIMEZONE"))
    auth_enabled: bool = Field(default=False, validation_alias=AliasChoices("AUTH_ENABLED", "SPARC_AUTH_ENABLED"))
    auth_username: str | None = Field(default=None, validation_alias=AliasChoices("AUTH_USERNAME", "SPARC_AUTH_USERNAME"))
    auth_password: str | None = Field(default=None, validation_alias=AliasChoices("AUTH_PASSWORD", "SPARC_AUTH_PASSWORD"))
    auth_session_secret: str | None = Field(default=None, validation_alias=AliasChoices("AUTH_SESSION_SECRET", "SPARC_AUTH_SESSION_SECRET"))
    auth_session_minutes: int = Field(default=720, validation_alias=AliasChoices("AUTH_SESSION_MINUTES", "SPARC_AUTH_SESSION_MINUTES"))
    entra_enabled: bool = Field(default=False, validation_alias=AliasChoices("ENTRA_ENABLED", "SPARC_ENTRA_ENABLED"))
    entra_tenant_id: str | None = Field(default=None, validation_alias=AliasChoices("ENTRA_TENANT_ID", "SPARC_ENTRA_TENANT_ID"))
    entra_client_id: str | None = Field(default=None, validation_alias=AliasChoices("ENTRA_CLIENT_ID", "SPARC_ENTRA_CLIENT_ID"))
    entra_client_secret: str | None = Field(default=None, validation_alias=AliasChoices("ENTRA_CLIENT_SECRET", "SPARC_ENTRA_CLIENT_SECRET"))
    entra_redirect_uri: str | None = Field(default=None, validation_alias=AliasChoices("ENTRA_REDIRECT_URI", "SPARC_ENTRA_REDIRECT_URI"))
    entra_authority_url: str | None = Field(default=None, validation_alias=AliasChoices("ENTRA_AUTHORITY_URL", "SPARC_ENTRA_AUTHORITY_URL"))
    entra_post_logout_redirect_uri: str | None = Field(default=None, validation_alias=AliasChoices("ENTRA_POST_LOGOUT_REDIRECT_URI", "SPARC_ENTRA_POST_LOGOUT_REDIRECT_URI"))

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
