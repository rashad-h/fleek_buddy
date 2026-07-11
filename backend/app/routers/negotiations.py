from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent import negotiator
from app.db import get_session
from app.models import Item, Message, Negotiation
from app.schemas import BuyerMessage, NegotiationCreate, NegotiationDetail, NegotiationRead

router = APIRouter(prefix="/negotiations", tags=["negotiations"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def _load_negotiation(session: AsyncSession, negotiation_id: int) -> Negotiation:
    result = await session.execute(
        select(Negotiation)
        .options(selectinload(Negotiation.messages), selectinload(Negotiation.item))
        .where(Negotiation.id == negotiation_id)
    )
    negotiation = result.scalar_one_or_none()
    if negotiation is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return negotiation


def _require_open(negotiation: Negotiation) -> None:
    if negotiation.status != "open":
        raise HTTPException(status_code=409, detail=f"Negotiation is {negotiation.status}")


def _agent_response(session: AsyncSession, negotiation: Negotiation) -> StreamingResponse:
    return StreamingResponse(
        negotiator.respond_stream(
            session, negotiation.item, negotiation, list(negotiation.messages)
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@router.post("", response_model=NegotiationRead, status_code=201)
async def create_negotiation(
    data: NegotiationCreate, session: AsyncSession = Depends(get_session)
) -> Negotiation:
    """Open a negotiation with the buyer's first offer. No agent call yet:
    the client follows up with POST /negotiations/{id}/respond."""
    item = await session.get(Item, data.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    offer = Decimal(str(data.offer_price)).quantize(Decimal("0.01"))
    negotiation = Negotiation(item_id=item.id, buyer_id=data.buyer_id, current_offer=offer)
    session.add(negotiation)
    await session.flush()

    content = data.message or (f"Hi! I'd like to offer £{offer} for the full bundle.")
    session.add(
        Message(
            negotiation_id=negotiation.id,
            role="buyer",
            content=content,
            offer_amount=offer,
            action="offer",
        )
    )
    await session.commit()
    await session.refresh(negotiation)
    return negotiation


@router.get("/{negotiation_id}", response_model=NegotiationDetail)
async def get_negotiation(
    negotiation_id: int, session: AsyncSession = Depends(get_session)
) -> Negotiation:
    return await _load_negotiation(session, negotiation_id)


@router.post("/{negotiation_id}/respond")
async def respond(
    negotiation_id: int, session: AsyncSession = Depends(get_session)
) -> StreamingResponse:
    """Stream the agent's reaction to the current negotiation state."""
    negotiation = await _load_negotiation(session, negotiation_id)
    _require_open(negotiation)
    return _agent_response(session, negotiation)


@router.post("/{negotiation_id}/messages")
async def send_message(
    negotiation_id: int,
    data: BuyerMessage,
    session: AsyncSession = Depends(get_session),
) -> StreamingResponse:
    """Persist a buyer message (optionally a new offer), then stream the reply."""
    negotiation = await _load_negotiation(session, negotiation_id)
    _require_open(negotiation)

    offer = (
        Decimal(str(data.offer_amount)).quantize(Decimal("0.01"))
        if data.offer_amount is not None
        else None
    )
    if not data.content.strip() and offer is None:
        raise HTTPException(status_code=422, detail="Message needs text or an offer")

    content = data.content.strip() or f"I can do £{offer} for the bundle."
    message = Message(
        negotiation_id=negotiation.id,
        role="buyer",
        content=content,
        offer_amount=offer,
        action="offer" if offer is not None else None,
    )
    if offer is not None:
        negotiation.current_offer = offer
    session.add(message)
    await session.commit()

    negotiation = await _load_negotiation(session, negotiation_id)
    return _agent_response(session, negotiation)
