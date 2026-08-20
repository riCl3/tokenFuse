from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class ProjectDashboardRow(BaseModel):
    """One row of the operator dashboard's project list."""

    id: int
    name: str
    monthly_budget_usd: Decimal
    is_active: bool
    created_at: datetime
    total_requests: int
    total_cost_usd: Decimal
    total_tokens: int
    window_used_units: int
    window_budget_units: int
    window_status: str


class ModelUsageRow(BaseModel):
    """Per-model aggregate for a single project."""

    model: str
    requests: int
    cost_usd: Decimal
    total_tokens: int


class UsageSummary(BaseModel):
    """Detailed usage view for a single project."""

    project_id: int
    project_name: str
    totals: dict
    by_model: list[ModelUsageRow]
    last_24h_cost_usd: Decimal
    window_used_units: int
    window_budget_units: int
    window_status: str