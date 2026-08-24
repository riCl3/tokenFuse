"""Operator dashboard endpoints.

These are read-only views for the (single-operator) MVP dashboard. They require
a valid API key but intentionally do NOT enforce per-project ownership: a
dashboard implies seeing everything. Tightening this to per-project keys or an
admin key type is on the roadmap.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_dep
from app.core.config import get_settings
from app.db.deps import get_db
from app.db.models import Project, UsageEvent, User
from app.schemas.dashboard import (
    ModelUsageRow,
    ProjectDashboardRow,
    UsageSummary,
)
from app.services import budget_service, usage_service

settings = get_settings()

router = APIRouter(tags=["dashboard"])


@router.get("/v1/projects", response_model=list[ProjectDashboardRow])
async def list_projects(
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectDashboardRow]:
    projects = (
        await db.execute(
            select(Project)
            .where(Project.owner_id == user.id)
            .order_by(Project.created_at.desc())
        )
    ).scalars().all()

    # One grouped query covers every project's totals (avoids an N+1 SELECT).
    agg_rows = (
        await db.execute(
            select(
                UsageEvent.project_id,
                func.count(UsageEvent.id),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
            ).group_by(UsageEvent.project_id)
        )
    ).all()
    agg = {row[0]: (row[1], row[2], row[3]) for row in agg_rows}

    rows = []
    for project in projects:
        requests, cost, tokens = agg.get(project.id, (0, Decimal("0"), 0))
        budget_units = budget_service.window_budget_units(
            float(project.monthly_budget_usd), settings.budget_window_seconds
        )
        window = await budget_service.check_budget(
            project.id, budget_units, project.warn_pct
        )
        rows.append(
            ProjectDashboardRow(
                id=project.id,
                name=project.name,
                monthly_budget_usd=project.monthly_budget_usd,
                is_active=project.is_active,
                created_at=project.created_at,
                total_requests=requests,
                total_cost_usd=cost,
                total_tokens=tokens,
                window_used_units=window.used_units,
                window_budget_units=window.budget_units,
                window_status=window.status,
            )
        )
    return rows


@router.get("/v1/usage/{project_id}", response_model=UsageSummary)
async def project_usage(
    project_id: int,
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> UsageSummary:
    project = (
        await db.execute(
            select(Project).where(Project.id == project_id, Project.owner_id == user.id)
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )

    totals = await usage_service.project_totals(db, project_id)
    by_model = await usage_service.usage_by_model(db, project_id)
    last_24h = await usage_service.spend_since(
        db, project_id, datetime.now(timezone.utc) - timedelta(hours=24)
    )
    budget_units = budget_service.window_budget_units(
        float(project.monthly_budget_usd), settings.budget_window_seconds
    )
    window = await budget_service.check_budget(
        project_id, budget_units, project.warn_pct
    )

    return UsageSummary(
        project_id=project.id,
        project_name=project.name,
        totals=totals,
        by_model=by_model,
        last_24h_cost_usd=last_24h,
        window_used_units=window.used_units,
        window_budget_units=window.budget_units,
        window_status=window.status,
    )