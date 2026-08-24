from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Provider keys are stored as-is (reversible, since the proxy must send them
# upstream). They are masked in API responses to avoid leaking secrets.
ALLOWED_PROVIDERS = ("openai", "openrouter", "grok", "groq")


def _mask_key(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    monthly_budget_usd: Decimal | None = None
    warn_pct: float | None = Field(default=None, ge=0.1, le=0.99)
    fallback_model: str | None = None
    custom_pricing: dict[str, dict[str, float]] | None = None
    provider_keys: dict[str, str] | None = None

    @model_validator(mode="after")
    def _check_providers(self):
        if self.provider_keys is not None:
            for k in self.provider_keys:
                if k not in ALLOWED_PROVIDERS:
                    raise ValueError(
                        f"Unknown provider '{k}'. Allowed: {', '.join(ALLOWED_PROVIDERS)}"
                    )
        return self


class ApiKeySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    label: str | None
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    monthly_budget_usd: Decimal
    warn_pct: float
    fallback_model: str | None
    custom_pricing: dict | None = None
    provider_keys: dict | None = None
    is_active: bool
    created_at: datetime
    api_keys: list[ApiKeySummary] = []

    @model_validator(mode="after")
    def _mask(self):
        if self.provider_keys:
            self.provider_keys = {k: _mask_key(v) for k, v in self.provider_keys.items()}
        return self


class ProjectCreatedResponse(BaseModel):
    project: ProjectResponse
    api_key: str