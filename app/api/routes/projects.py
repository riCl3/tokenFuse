from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_project
from app.db.deps import get_db
from app.schemas.project import (
    ProjectCreate,
    ProjectCreatedResponse,
    ProjectResponse,
)
from app.services import project_service

router = APIRouter(prefix="/v1/projects", tags=["projects"])


@router.post(
    "",
    response_model=ProjectCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
) -> ProjectCreatedResponse:
    project, raw_key = await project_service.create_project(db, payload)
    return ProjectCreatedResponse(
        project=ProjectResponse.model_validate(project),
        api_key=raw_key,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    auth: AuthContext = Depends(get_current_project),
) -> ProjectResponse:
    if auth.project.id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this project",
        )
    return auth.project