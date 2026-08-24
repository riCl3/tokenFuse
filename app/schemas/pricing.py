from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PricingCreate(BaseModel):
    model: str = Field(min_length=1, max_length=120)
    input_price: Decimal = Field(ge=0, le=1000, decimal_places=4)
    output_price: Decimal = Field(ge=0, le=1000, decimal_places=4)


class PricingUpdate(BaseModel):
    input_price: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=4)
    output_price: Decimal | None = Field(default=None, ge=0, le=1000, decimal_places=4)
    is_active: bool | None = None


class PricingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    model: str
    input_price: Decimal
    output_price: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectPricingUpdate(BaseModel):
    """Per-project overrides: dict of model -> {input, output} or null to clear."""

    custom_pricing: dict[str, dict[str, float]] | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    monthly_budget_usd: Decimal | None = None
    warn_pct: float | None = Field(default=None, ge=0.1, le=0.99)
    fallback_model: str | None = None
    is_active: bool | None = None
    custom_pricing: dict[str, dict[str, float]] | None = None
