from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_dep
from app.db.deps import get_db
from app.db.models import ModelPricing, User
from app.schemas.pricing import PricingCreate, PricingResponse, PricingUpdate

router = APIRouter(prefix="/v1/pricing", tags=["pricing"])


@router.get("", response_model=list[PricingResponse])
async def list_pricing(
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> list[ModelPricing]:
    rows = (await db.execute(select(ModelPricing).order_by(ModelPricing.model))).scalars().all()
    return list(rows)


@router.post("", response_model=PricingResponse, status_code=status.HTTP_201_CREATED)
async def create_pricing(
    payload: PricingCreate,
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> ModelPricing:
    existing = (
        await db.execute(select(ModelPricing).where(ModelPricing.model == payload.model))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Pricing for model '{payload.model}' already exists. Use PUT to update.")
    row = ModelPricing(
        model=payload.model,
        input_price=payload.input_price,
        output_price=payload.output_price,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


@router.put("/{model:path}", response_model=PricingResponse)
async def upsert_pricing(
    model: str,
    payload: PricingUpdate,
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> ModelPricing:
    row = (
        await db.execute(select(ModelPricing).where(ModelPricing.model == model))
    ).scalar_one_or_none()
    if not row:
        if payload.input_price is None or payload.output_price is None:
            raise HTTPException(status_code=404, detail=f"No pricing for model '{model}'")
        row = ModelPricing(model=model, input_price=payload.input_price, output_price=payload.output_price)
        if payload.is_active is not None:
            row.is_active = payload.is_active
        db.add(row)
    else:
        if payload.input_price is not None:
            row.input_price = payload.input_price
        if payload.output_price is not None:
            row.output_price = payload.output_price
        if payload.is_active is not None:
            row.is_active = payload.is_active
    await db.commit()
    await db.refresh(row)
    return row


@router.delete("/{model:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pricing(
    model: str,
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(ModelPricing).where(ModelPricing.model == model))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(row)
    await db.commit()
