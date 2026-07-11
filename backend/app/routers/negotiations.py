from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent import negotiator, pricing
from app.db import get_session
from app.models import Item, Message, Negotiation, SelectionEntry
from app.schemas import (
    BuyerMessage,
    NegotiationCreate,
    NegotiationDetail,
    NegotiationRead,
    OfferSelection,
)

router = APIRouter(prefix="/negotiations", tags=["negotiations"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


async def _load_negotiation(session: AsyncSession, negotiation_id: int) -> Negotiation:
    # populate_existing: with expire_on_commit=False the identity map would
    # otherwise return the instance with its pre-commit (stale) messages
    # collection, and the agent would never see the newest buyer message.
    result = await session.execute(
        select(Negotiation)
        .options(selectinload(Negotiation.messages), selectinload(Negotiation.item))
        .where(Negotiation.id == negotiation_id)
        .execution_options(populate_existing=True)
    )
    negotiation = result.scalar_one_or_none()
    if negotiation is None:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    return negotiation


def _require_open(negotiation: Negotiation) -> None:
    if negotiation.status != "open":
        raise HTTPException(status_code=409, detail=f"Negotiation is {negotiation.status}")


def _selection_entries(
    selection: list[OfferSelection] | None,
) -> list[SelectionEntry] | None:
    if not selection:
        return None
    return pricing.normalize([entry.model_dump() for entry in selection])


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
    selection = _selection_entries(data.selection)
    negotiation = Negotiation(
        item_id=item.id,
        buyer_id=data.buyer_id,
        current_offer=offer,
        current_selection=selection,
    )
    session.add(negotiation)
    await session.flush()

    content = data.message or (
        f"Hi! I'd like to offer £{offer} for {pricing.describe_selection(selection)}."
    )
    session.add(
        Message(
            negotiation_id=negotiation.id,
            role="buyer",
            content=content,
            offer_amount=offer,
            offer_selection=selection,
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

    # A new selection only takes effect together with a new offer amount.
    selection = _selection_entries(data.selection) if offer is not None else None
    if offer is not None and selection is not None:
        negotiation.current_selection = selection
    scope = negotiation.current_selection

    content = data.content.strip() or (
        f"I can do £{offer} for {pricing.describe_selection(scope)}."
    )
    message = Message(
        negotiation_id=negotiation.id,
        role="buyer",
        content=content,
        offer_amount=offer,
        offer_selection=scope if offer is not None else None,
        action="offer" if offer is not None else None,
    )
    if offer is not None:
        negotiation.current_offer = offer
    session.add(message)
    await session.commit()

    negotiation = await _load_negotiation(session, negotiation_id)
    return _agent_response(session, negotiation)


@router.post("/{negotiation_id}/accept", response_model=NegotiationDetail)
async def accept_counter(
    negotiation_id: int, session: AsyncSession = Depends(get_session)
) -> Negotiation:
    """The buyer accepts the seller's standing counter-offer; locks the deal."""
    negotiation = await _load_negotiation(session, negotiation_id)
    _require_open(negotiation)

    counter = next(
        (
            m
            for m in reversed(negotiation.messages)
            if m.role == "agent" and m.action == "counter" and m.offer_amount is not None
        ),
        None,
    )
    if counter is None:
        raise HTTPException(status_code=409, detail="No seller offer to accept")

    negotiation.status = "accepted"
    negotiation.current_offer = counter.offer_amount
    negotiation.current_selection = counter.offer_selection
    negotiation.agreed_price = counter.offer_amount
    session.add(
        Message(
            negotiation_id=negotiation.id,
            role="buyer",
            content=(
                f"Deal — £{counter.offer_amount} for "
                f"{pricing.describe_selection(counter.offer_selection)}."
            ),
            offer_amount=counter.offer_amount,
            offer_selection=counter.offer_selection,
            action="accept",
        )
    )
    await session.commit()
    return await _load_negotiation(session, negotiation_id)
