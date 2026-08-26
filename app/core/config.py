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
    affiliate_provider: str = ""  # "product_search" | "amazon"
    affiliate_api_key: str = ""  # Amazon Access Key ID (for "amazon")
    affiliate_api_secret: str = ""  # Amazon Secret Access Key (for "amazon")
    affiliate_partner_id: str = ""  # Amazon Associates tag (e.g. "mytag-21")
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


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (single source of truth)."""
    return Settings()


settings = get_settings()