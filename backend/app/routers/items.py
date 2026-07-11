from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Item, Negotiation
from app.schemas import ItemRead, NegotiationRead

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemRead])
async def list_items(session: AsyncSession = Depends(get_session)) -> list[Item]:
    result = await session.execute(select(Item).order_by(Item.id))
    return list(result.scalars().all())


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)) -> Item:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/{item_id}/negotiation", response_model=NegotiationRead)
async def get_negotiation_for_item(
    item_id: int, buyer_id: str, session: AsyncSession = Depends(get_session)
) -> Negotiation:
    """Latest negotiation between this buyer and item; 404 when none exists."""
    result = await session.execute(
        select(Negotiation)
        .where(Negotiation.item_id == item_id, Negotiation.buyer_id == buyer_id)
        .order_by(Negotiation.id.desc())
        .limit(1)
    )
    negotiation = result.scalar_one_or_none()
    if negotiation is None:
        raise HTTPException(status_code=404, detail="No negotiation for this buyer")
    return negotiation
