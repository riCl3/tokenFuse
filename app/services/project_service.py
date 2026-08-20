from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import generate_api_key, hash_api_key
from app.db.models import ApiKey, Project
from app.schemas.project import ProjectCreate

settings = get_settings()


async def create_project(
    session: AsyncSession, data: ProjectCreate
) -> tuple[Project, str]:
    project = Project(
        name=data.name,
        monthly_budget_usd=(
            data.monthly_budget_usd
            if data.monthly_budget_usd is not None
            else settings.default_monthly_budget_usd
        ),
        warn_pct=(
            data.warn_pct if data.warn_pct is not None else settings.budget_warn_pct
        ),
        fallback_model=data.fallback_model,
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