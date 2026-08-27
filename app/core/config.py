"""Application configuration loaded from environment variables.

All secrets and environment-specific values are read from the process
environment (or a `.env` file), never hardcoded.
"""

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: object) -> object:
    """Normalize PostgreSQL URLs for SQLAlchemy's asyncpg dialect."""
    if not isinstance(value, str):
        return value

    url = value.strip()
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif not url.startswith("postgresql+asyncpg://") and url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    elif url.startswith("postgresql+"):
        url = "postgresql+asyncpg://" + url.split("://", 1)[1]
    elif not url.startswith("postgresql+asyncpg://"):
        return value

    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    if any(key == "sslmode" for key, _ in query):
        # libpq uses sslmode; asyncpg accepts the equivalent ssl argument.
        has_ssl = any(key == "ssl" for key, _ in query)
        query = [
            ("ssl" if key == "sslmode" and not has_ssl else key, val)
            for key, val in query
            if key != "sslmode" or not has_ssl
        ]
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url


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
    frontend_url: str = "http://localhost:5173"

    # TrendEra autonomous workflow
    min_opportunity_score: int = 0  # 0 = never block weak opportunities
    product_republish_cooldown_days: int = 30

    # Security
    secret_key: str = Field(default="dev-insecure-secret-key-change-me")

    # Database.
    # Local development defaults to a file-backed SQLite database so the app
    # runs without PostgreSQL. Set DATABASE_URL to a PostgreSQL asyncpg URL
    # for Render/production; this is always environment-configurable.
    database_url: str = Field(
        default="sqlite+aiosqlite:///./dev.db"
    )

    # Redis (future infrastructure; not used by Phase 1 execution)
    redis_url: str = "redis://localhost:6379/0"

    # LLM (DeepSeek-ready; leave empty to use the deterministic mock)
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    # Affiliate offer discovery (all optional; the app runs without them).
    # When unconfigured, automatic affiliate discovery gracefully returns
    # "not_found" and the article is still generated/published without a CTA.
    affiliate_provider: str = ""  # "amazon" | "product_search" (legacy fallback)
    affiliate_api_key: str = ""  # Amazon Creators API Credential ID (client_id)
    affiliate_api_secret: str = ""  # Amazon Creators API Credential Secret (client_secret)
    affiliate_api_version: str = ""  # Optional Amazon Creators API credential version (3.1 / 3.2 / 3.3)
    affiliate_partner_id: str = ""  # Amazon Associates Partner Tag (tracking ID)
    affiliate_api_base_url: str = ""
    affiliate_marketplace: str = ""  # e.g. "www.amazon.sa" or "www.amazon.com"
    min_affiliate_match_score: int = 70

    # Google OAuth 2.0 (Blogger API v3)
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = "http://localhost:8000/auth/blogger/callback"
    google_blog_id: str = ""
    google_refresh_token: str = ""

    # Logging
    log_level: str = "INFO"
    log_format: str = "text"  # "text" or "json"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value):
        """Force PostgreSQL URLs onto the asyncpg driver (async SQLAlchemy)."""
        return normalize_database_url(value)


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()


settings = get_settings()
