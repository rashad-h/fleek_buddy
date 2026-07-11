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
from app.agent import pricing
from app.agent.context import NegotiationContext, build_chat_messages
from app.agent.policy import (
    GuardedDecision,
    apply_guardrails,
    fallback_reply,
    firm_price_reply,
)
from app.agent.prompts import VOICE_NOTE
from app.agent.schemas import AgentDecision
from app.models import Item, Message, Negotiation

logger = logging.getLogger(__name__)

TOKEN_DELAY_SECONDS = 0.02


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _needs_firm_reply(ctx: NegotiationContext) -> bool:
    offer = ctx.negotiation.current_offer
    if ctx.item.negotiable or offer is None:
        return False
    asking = pricing.selection_asking(ctx.item, ctx.negotiation.current_selection)
    return offer < asking


async def decide(ctx: NegotiationContext) -> AgentDecision:
    """Produce the guarded decision for the current negotiation state."""
    if _needs_firm_reply(ctx):
        guarded = firm_price_reply(ctx)
    else:
        try:
            raw = await llm.complete_structured(build_chat_messages(ctx), AgentDecision)
        except Exception:
            logger.exception("agent LLM call failed; using fallback reply")
            return fallback_reply()
        guarded = apply_guardrails(raw, ctx)
        logger.info(
            "raw LLM decision: %s £%s %s | guarded: %s £%s | voice_note: %s",
            raw.action,
            raw.price,
            raw.selection,
            guarded.decision.action,
            guarded.decision.price,
            guarded.voice_note,
        )
    if guarded.voice_note is None:
        return guarded.decision
    return await _voice(ctx, guarded)


async def _voice(ctx: NegotiationContext, guarded: GuardedDecision) -> AgentDecision:
    """Have the LLM word an overridden decision in the seller's voice.

    Guardrails change numbers, not words: when they rewrite a decision the
    LLM's original message no longer matches it, so this second call asks
    the model to announce the final decision itself. The canned message
    already on the decision is kept if the call fails or misbehaves.
    """
    note = VOICE_NOTE.format(decision=guarded.voice_note)
    messages = [*build_chat_messages(ctx), {"role": "user", "content": note}]
    try:
        text = (await llm.complete(messages)).strip()
    except Exception:
        logger.exception("voice pass failed; using canned message")
        return guarded.decision
    if text.startswith("{"):
        # A model stuck in output-format mode; salvage the message field.
        try:
            text = str(json.loads(text).get("message", ""))
        except ValueError:
            text = ""
    text = text.strip().strip('"')
    if not text:
        return guarded.decision
    return guarded.decision.model_copy(update={"message": text})


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

    if decision.action == "counter":
        # A counter without its own selection applies to the buyer's scope;
        # store that scope so later turns compare like with like.
        counter_selection = (
            [entry.model_dump() for entry in decision.selection]
            if decision.selection
            else negotiation.current_selection
        )
    else:
        counter_selection = None

    message = Message(
        negotiation_id=negotiation.id,
        role="agent",
        content=decision.message,
        offer_amount=(Decimal(str(decision.price)) if decision.action == "counter" else None),
        offer_selection=counter_selection,
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
            "selection": stored.offer_selection,
            "status": negotiation.status,
            "message_id": stored.id,
        },
    )
    yield _sse("done", {})
