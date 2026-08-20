from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "TokenFuse"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/tokenfuse"
    )
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    openrouter_api_key: str = ""

    telegram_bot_token: str = ""
    alert_webhook_url: str = ""

    default_monthly_budget_usd: float = 50.0
    budget_warn_pct: float = 0.8
    fallback_model: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()