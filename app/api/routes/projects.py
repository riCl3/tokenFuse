from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthContext, get_current_project
from app.db.deps import get_db
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


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: int,
    payload: ProjectUpdate,
    auth: AuthContext = Depends(get_current_project),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    if auth.project.id != project_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized for this project",
        )
    # Validate custom_pricing shape if provided
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

    updated = await project_service.update_project(db, auth.project, payload)
    return updated