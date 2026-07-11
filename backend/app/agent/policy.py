"""Deterministic guardrails applied on top of every LLM decision.

The LLM proposes; this module disposes. Whatever the model hallucinates,
these rules guarantee the seller never sells below the floor, counters stay
inside sensible bounds, and concessions only ever move downwards.
"""

from decimal import Decimal

from app.agent.context import NegotiationContext
from app.agent.schemas import AgentDecision

TWO_PLACES = Decimal("0.01")


def _to_money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES)


def previous_counter(ctx: NegotiationContext) -> Decimal | None:
    """The agent's most recent counter-offer, if any."""
    for message in reversed(ctx.messages):
        if message.role == "agent" and message.action == "counter":
            if message.offer_amount is not None:
                return message.offer_amount
    return None


def firm_price_reply(ctx: NegotiationContext) -> AgentDecision:
    """Canned response for non-negotiable listings offered below asking."""
    item = ctx.item
    return AgentDecision(
        action="chat",
        price=None,
        message=(
            f"Appreciate the interest, but the price on this one is firm at "
            f"£{item.bundle_price} — {item.condition} {item.brand} at "
            f"£{item.price_per_piece}/piece is already sharp. Happy to answer "
            f"any questions about the bundle."
        ),
    )


def fallback_reply() -> AgentDecision:
    """Safe response when the LLM call or parsing fails; keeps the demo alive."""
    return AgentDecision(
        action="chat",
        price=None,
        message=(
            "Sorry, I lost my train of thought there. Could you repeat your offer for the bundle?"
        ),
    )


def apply_guardrails(decision: AgentDecision, ctx: NegotiationContext) -> AgentDecision:
    """Clamp an LLM decision to the item's haggle policy.

    Rules, in order:
    - accept without a standing offer becomes a chat asking for a number
    - accept below the floor becomes a counter at max(floor, midpoint)
    - counters are clamped to [floor, asking] and never rise above the
      agent's previous counter (concessions are monotonic)
    - a counter at or below the buyer's valid standing offer becomes an accept
    """
    item = ctx.item
    floor = item.lowest_bundle_price
    asking = item.bundle_price
    offer = ctx.negotiation.current_offer
    prev = previous_counter(ctx)
    ceiling = min(asking, prev) if prev is not None else asking

    if decision.action == "accept":
        if offer is None:
            return AgentDecision(
                action="chat",
                price=None,
                message="Sounds promising — what price did you have in mind for the bundle?",
            )
        if offer < floor:
            counter = max(floor, _to_money((offer + ceiling) / 2))
            return AgentDecision(
                action="counter",
                price=float(counter),
                message=(
                    f"I can't go quite that low, but let's make it work — "
                    f"£{counter} for the full bundle and we have a deal."
                ),
            )
        return decision

    if decision.action == "counter":
        price = _to_money(decision.price) if decision.price is not None else ceiling
        price = max(floor, min(price, ceiling))
        if offer is not None and offer >= floor and offer >= price:
            return AgentDecision(
                action="accept",
                price=None,
                message=f"You know what — £{offer} works. Deal!",
            )
        return AgentDecision(action="counter", price=float(price), message=decision.message)

    return decision
