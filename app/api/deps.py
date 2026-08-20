from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_api_key
from app.db.deps import get_db
from app.db.models import ApiKey, Project

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    project: Project
    api_key: ApiKey


async def get_current_project(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
) -> AuthContext:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_hash = hash_api_key(credentials.credentials)
    stmt = (
        select(ApiKey)
        .where(ApiKey.key_hash == key_hash)
        .options(selectinload(ApiKey.project).selectinload(Project.api_keys))
    )
    api_key = (await session.execute(stmt)).scalar_one_or_none()

    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not api_key.is_active or not api_key.project.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key or project is disabled",
        )
    return AuthContext(project=api_key.project, api_key=api_key)