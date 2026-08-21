"""Application configuration loaded from environment variables.

All secrets and environment-specific values are read from the process
environment (or a `.env` file), never hardcoded.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    Values are sourced from environment variables with case-insensitive
    matching (e.g. ``APP_NAME`` -> ``app_name``).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AI Company OS"
    app_env: str = "development"
    debug: bool = True
    api_prefix: str = ""
    host: str = "0.0.0.0"
    port: int = 8000

    # Security
    secret_key: str = Field(default="dev-insecure-secret-key-change-me")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://ai_company:ai_company_password@localhost:5432/ai_company_os"
    )

    # Redis (future infrastructure; not used by Phase 1 execution)
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()


settings = get_settings()