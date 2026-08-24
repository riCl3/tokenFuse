from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.security import generate_api_key, hash_api_key
from app.db.models import ApiKey, Project
from app.schemas.project import ALLOWED_PROVIDERS, ProjectCreate

settings = get_settings()


def _normalize_provider_keys(raw: dict[str, str] | None) -> dict | None:
    if raw is None:
        return None
    cleaned = {}
    for k, v in raw.items():
        if k not in ALLOWED_PROVIDERS:
            continue
        # Empty string clears a previously set key.
        if v is None or v == "":
            continue
        cleaned[k] = v
    return cleaned or None


async def create_project(
    session: AsyncSession, data: ProjectCreate, owner_id: int | None = None
) -> tuple[Project, str]:
    # Validate custom_pricing if provided
    custom = getattr(data, "custom_pricing", None)
    if custom is not None and len(custom) == 0:
        custom = None
    provider_keys = _normalize_provider_keys(getattr(data, "provider_keys", None))
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
        provider_keys=provider_keys,
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
    if data.provider_keys is not None:
        # Merge: keep existing providers not mentioned; blank value clears one.
        merged = dict(project.provider_keys or {})
        for provider, value in data.provider_keys.items():
            if provider not in ALLOWED_PROVIDERS:
                continue
            if value is None or value == "":
                merged.pop(provider, None)
            else:
                merged[provider] = value
        project.provider_keys = merged or None
    await session.commit()
    await session.refresh(project)
    # Re-load with api_keys for response
    refreshed = (
        await session.execute(
            select(Project).where(Project.id == project.id).options(selectinload(Project.api_keys))
        )
    ).scalar_one()
    return refreshed