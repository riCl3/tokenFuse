"""Write + read-side queries for UsageEvent rows (the dashboard's data source).

The proxy records one UsageEvent per completed call (streamed or not). The
read functions here back the dashboard endpoints with grouped SQL aggregates.
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageEvent

logger = logging.getLogger(__name__)


async def persist_usage_event(
    session: AsyncSession,
    *,
    project_id: int,
    api_key_id: int | None,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    cost_usd: float,
    request_id: str | None = None,
    streamed: bool = False,
) -> None:
    """Insert one UsageEvent row. Callers wrap this so a failure to persist
    bookkeeping never fails the LLM request itself."""
    session.add(
        UsageEvent(
            project_id=project_id,
            api_key_id=api_key_id,
            provider=provider,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            cost_usd=Decimal(str(cost_usd)),
            request_id=request_id,
            streamed=streamed,
        )
    )
    await session.commit()


async def project_totals(session: AsyncSession, project_id: int) -> dict:
    """One row of totals for a project: request count, cost, tokens."""
    row = (
        await session.execute(
            select(
                func.count(UsageEvent.id),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
            ).where(UsageEvent.project_id == project_id)
        )
    ).one()
    return {
        "requests": row[0],
        "cost_usd": row[1],
        "total_tokens": row[2],
    }


async def usage_by_model(session: AsyncSession, project_id: int) -> list[dict]:
    """Per-model breakdown for a project, most expensive first."""
    rows = (
        await session.execute(
            select(
                UsageEvent.model,
                func.count(UsageEvent.id),
                func.coalesce(func.sum(UsageEvent.cost_usd), 0),
                func.coalesce(func.sum(UsageEvent.total_tokens), 0),
            )
            .where(UsageEvent.project_id == project_id)
            .group_by(UsageEvent.model)
            .order_by(func.sum(UsageEvent.cost_usd).desc())
        )
    ).all()
    return [
        {
            "model": r[0],
            "requests": r[1],
            "cost_usd": r[2],
            "total_tokens": r[3],
        }
        for r in rows
    ]


async def spend_since(session: AsyncSession, project_id: int, cutoff: datetime) -> Decimal:
    """Total spend for a project since an arbitrary cutoff (e.g. last 24h)."""
    return (
        await session.execute(
            select(func.coalesce(func.sum(UsageEvent.cost_usd), 0)).where(
                UsageEvent.project_id == project_id,
                UsageEvent.created_at >= cutoff,
            )
        )
    ).scalar_one()