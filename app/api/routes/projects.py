from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import AuthContext, get_current_user_or_project
from app.db.deps import get_db
from app.db.models import Project
from app.schemas.pricing import ProjectUpdate
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
    auth_tuple: tuple = Depends(get_current_user_or_project),
    db: AsyncSession = Depends(get_db),
) -> ProjectCreatedResponse:
    user, _ = auth_tuple
    if user is None:
        raise HTTPException(status_code=401, detail="JWT token required to create projects")
    project, raw_key = await project_service.create_project(db, payload, owner_id=user.id)
    return ProjectCreatedResponse(
        project=ProjectResponse.model_validate(project),
        api_key=raw_key,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    auth_tuple: tuple = Depends(get_current_user_or_project),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    user, auth_ctx = auth_tuple
    stmt = select(Project).where(Project.id == project_id).options(selectinload(Project.api_keys))
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if user is not None:
        if project.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    elif auth_ctx is not None:
        if auth_ctx.project.id != project_id:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    auth_tuple: tuple = Depends(get_current_user_or_project),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    user, auth_ctx = auth_tuple
    stmt = select(Project).where(Project.id == project_id).options(selectinload(Project.api_keys))
    project = (await db.execute(stmt)).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if user is not None:
        if project.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    elif auth_ctx is not None:
        if auth_ctx.project.id != project_id:
            raise HTTPException(status_code=403, detail="Not authorized for this project")

    if payload.custom_pricing is not None:
        for model, price in payload.custom_pricing.items():
            if not isinstance(price, dict) or "input" not in price or "output" not in price:
                raise HTTPException(status_code=400, detail=f"Invalid pricing for model '{model}': must be {{'input': float, 'output': float}}")
            try:
                float(price["input"])
                float(price["output"])
            except Exception:
                raise HTTPException(status_code=400, detail=f"Invalid numeric pricing for '{model}'")
            if float(price["input"]) < 0 or float(price["output"]) < 0:
                raise HTTPException(status_code=400, detail=f"Prices must be >= 0 for '{model}'")

    updated = await project_service.update_project(db, project, payload)
    return updated


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: int,
    auth_tuple: tuple = Depends(get_current_user_or_project),
    db: AsyncSession = Depends(get_db),
) -> None:
    user, auth_ctx = auth_tuple
    project = (
        await db.execute(
            select(Project).where(Project.id == project_id).options(selectinload(Project.api_keys))
        )
    ).scalar_one_or_none()
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if user is not None:
        if project.owner_id != user.id:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    elif auth_ctx is not None:
        if auth_ctx.project.id != project_id:
            raise HTTPException(status_code=403, detail="Not authorized for this project")
    await db.delete(project)
    await db.commit()