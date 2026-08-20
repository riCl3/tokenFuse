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
    openai_base_url: str = "https://api.openai.com/v1"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    provider_timeout_seconds: float = 120.0

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    alert_webhook_url: str = ""

    alert_recent_window_seconds: int = 300
    alert_spike_multiplier: float = 5.0
    alert_min_spend_usd: float = 0.5
    alert_cooldown_seconds: int = 900
    alert_check_interval_seconds: int = 60

    default_monthly_budget_usd: float = 50.0
    budget_warn_pct: float = 0.8
    budget_window_seconds: int = 3600
    fallback_model: str = ""
    redis_eval_available: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()