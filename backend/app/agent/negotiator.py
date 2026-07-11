"""Orchestrates one agent turn and streams it to the client as SSE.

Two-phase design: a single non-streamed structured LLM call produces the full
decision; guardrails run and the outcome is persisted BEFORE anything is
streamed. The streamed text is therefore always consistent with the applied
decision. Tokens are then replayed word-by-word for the live-typing effect.

SSE contract (consumed by ui/src/lib/api.ts):
    event: token    data: {"text": "..."}
    event: decision data: {"action": ..., "price": ..., "status": ..., "message_id": ...}
    event: error    data: {"detail": "..."}
    event: done     data: {}
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app import llm
from app.agent.context import NegotiationContext, build_chat_messages
from app.agent.policy import (
    apply_guardrails,
    fallback_reply,
    firm_price_reply,
)
from app.agent.schemas import AgentDecision
from app.models import Item, Message, Negotiation

logger = logging.getLogger(__name__)

TOKEN_DELAY_SECONDS = 0.02


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _needs_firm_reply(ctx: NegotiationContext) -> bool:
    offer = ctx.negotiation.current_offer
    return not ctx.item.negotiable and offer is not None and offer < ctx.item.bundle_price


async def decide(ctx: NegotiationContext) -> AgentDecision:
    """Produce the guarded decision for the current negotiation state."""
    if _needs_firm_reply(ctx):
        return firm_price_reply(ctx)
    try:
        raw = await llm.complete_structured(build_chat_messages(ctx), AgentDecision)
    except Exception:
        logger.exception("agent LLM call failed; using fallback reply")
        return fallback_reply()
    return apply_guardrails(raw, ctx)


async def _persist(
    session: AsyncSession,
    negotiation: Negotiation,
    decision: AgentDecision,
) -> Message:
    """Store the agent message and apply the status transition."""
    if decision.action == "accept":
        negotiation.status = "accepted"
        negotiation.agreed_price = negotiation.current_offer
    elif decision.action == "reject":
        negotiation.status = "rejected"

    message = Message(
        negotiation_id=negotiation.id,
        role="agent",
        content=decision.message,
        offer_amount=(Decimal(str(decision.price)) if decision.action == "counter" else None),
        action=decision.action,
    )
    session.add(message)
    await session.commit()
    await session.refresh(message)
    return message


async def respond_stream(
    session: AsyncSession,
    item: Item,
    negotiation: Negotiation,
    messages: list[Message],
) -> AsyncIterator[str]:
    """Run one agent turn and yield it as SSE frames."""
    ctx = NegotiationContext(item=item, negotiation=negotiation, messages=messages)
    try:
        decision = await decide(ctx)
        stored = await _persist(session, negotiation, decision)
    except Exception:
        logger.exception("agent turn failed")
        yield _sse("error", {"detail": "The seller is unavailable right now."})
        yield _sse("done", {})
        return

    for word in decision.message.split(" "):
        yield _sse("token", {"text": word + " "})
        await asyncio.sleep(TOKEN_DELAY_SECONDS)

    yield _sse(
        "decision",
        {
            "action": decision.action,
            "price": decision.price,
            "status": negotiation.status,
            "message_id": stored.id,
        },
    )
    yield _sse("done", {})
