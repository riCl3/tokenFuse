from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import generate_api_key, hash_api_key
from app.db.models import ApiKey, Project
from app.schemas.project import ProjectCreate

settings = get_settings()


async def create_project(
    session: AsyncSession, data: ProjectCreate, owner_id: int | None = None
) -> tuple[Project, str]:
    # Validate custom_pricing if provided
    custom = getattr(data, "custom_pricing", None)
    if custom is not None and len(custom) == 0:
        custom = None
    project = Project(
        name=data.name,
        owner_id=owner_id,
        monthly_budget_usd=(
            data.monthly_budget_usd
            if data.monthly_budget_usd is not None
            else settings.default_monthly_budget_usd
        ),
        warn_pct=(
            data.warn_pct if data.warn_pct is not None else settings.budget_warn_pct
        ),
        fallback_model=data.fallback_model,
        custom_pricing=custom,
    )
    session.add(project)

    raw_key = generate_api_key()
    api_key = ApiKey(
        project=project,
        label="default",
        key_hash=hash_api_key(raw_key),
    )
    session.add(api_key)

    await session.commit()

    project = (
        await session.execute(
            select(Project)
            .where(Project.id == project.id)
            .options(selectinload(Project.api_keys))
        )
    ).scalar_one()
    return project, raw_key


async def get_project(session: AsyncSession, project_id: int) -> Project | None:
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(selectinload(Project.api_keys))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def update_project(session: AsyncSession, project: Project, data) -> Project:
    if data.name is not None:
        project.name = data.name
    if data.monthly_budget_usd is not None:
        project.monthly_budget_usd = data.monthly_budget_usd
    if data.warn_pct is not None:
        project.warn_pct = data.warn_pct
    if data.fallback_model is not None:
        # Allow clearing with empty string
        project.fallback_model = data.fallback_model if data.fallback_model != "" else None
    if data.is_active is not None:
        project.is_active = data.is_active
    if data.custom_pricing is not None:
        # Allow clearing with empty dict — treat as None (use global pricing)
        if len(data.custom_pricing) == 0:
            project.custom_pricing = None
        else:
            project.custom_pricing = data.custom_pricing
    await session.commit()
    await session.refresh(project)
    # Re-load with api_keys for response
    refreshed = (
        await session.execute(
            select(Project).where(Project.id == project.id).options(selectinload(Project.api_keys))
        )
    ).scalar_one()
    return refreshed