from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    monthly_budget_usd: Decimal | None = None
    warn_pct: float | None = Field(default=None, ge=0.1, le=0.99)
    fallback_model: str | None = None
    custom_pricing: dict[str, dict[str, float]] | None = None


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
    is_active: bool
    created_at: datetime
    api_keys: list[ApiKeySummary] = []


class ProjectCreatedResponse(BaseModel):
    project: ProjectResponse
    api_key: str