"""Deterministic guardrails applied on top of every LLM decision.

The LLM proposes; this module disposes. Whatever the model hallucinates,
these rules guarantee the seller never sells below the (flexed) floor for
the exact pieces on the table, counters stay inside sensible bounds, and
concessions on an unchanged scope only ever move downwards.

Guardrails decide numbers, not words: whenever a rule overrides the LLM's
decision, the returned `GuardedDecision.voice_note` describes the final
decision so the negotiator can ask the LLM to word it in the seller's own
voice. The canned message variants below are only the fallback for when
that second call fails.

The floor is applied with a small flex (`pricing.FLOOR_FLEX`): closing a
touch below the floor to hit a cleaner number is allowed, by design.
"""

import random
from dataclasses import dataclass
from decimal import Decimal

from app.agent import pricing
from app.agent.context import NegotiationContext
from app.agent.schemas import AgentDecision
from app.models import SelectionEntry

TWO_PLACES = Decimal("0.01")

# Canned replies come in variants so a guardrail firing twice in one chat
# doesn't repeat itself word for word.
ASK_FOR_NUMBER = (
    "Sounds promising — what number did you have in mind?",
    "Could work. What are you thinking price-wise?",
    "Go on then, give me a number.",
)
BELOW_FLOOR_COUNTER = (
    "I can't go quite that low, but let's make it work — £{price} for {scope} and we have a deal.",
    "That's under what these owe me, honestly. £{price} for {scope} and they're yours.",
    "You drive a hard bargain. Best I can do on {scope} is £{price} — meet me there?",
)
ACCEPT_OFFER = (
    "You know what — £{offer} works. Deal!",
    "Alright, £{offer} it is. I'll get them packed up.",
    "Go on then, £{offer} and we're done. Pleasure doing business.",
)
FIRM_PRICE = (
    "Appreciate the interest, but prices on this one are firm — {quote}, delivered. "
    "{condition} {brand} at this level is already sharp.",
    "This one's priced to sell as-is, I'm afraid: {quote}, delivered. "
    "Happy to answer anything about the stock though.",
    "No haggling on this listing — {quote}, shipping included. "
    "For {condition} {brand} that's honest money.",
)
FALLBACK = (
    "Sorry, I lost my train of thought there. Could you repeat your offer?",
    "Hang on, dropped my thread for a second — what were you offering again?",
)


def _pick(variants: tuple[str, ...], **kwargs: object) -> str:
    return random.choice(variants).format(**kwargs)


@dataclass
class GuardedDecision:
    """A final decision plus, when a rule overrode the LLM, a description of
    that decision for the voice pass. `voice_note is None` means the LLM's
    own message already matches the decision and can be sent as-is."""

    decision: AgentDecision
    voice_note: str | None = None


def _to_money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(TWO_PLACES)


def previous_counter(
    ctx: NegotiationContext,
) -> tuple[Decimal, list[SelectionEntry] | None] | None:
    """The agent's most recent counter (amount, selection), if any."""
    for message in reversed(ctx.messages):
        if message.role == "agent" and message.action == "counter":
            if message.offer_amount is not None:
                return message.offer_amount, pricing.normalize(message.offer_selection)
    return None


def _cap_selection(
    ctx: NegotiationContext, selection: list[SelectionEntry] | None
) -> list[SelectionEntry] | None:
    """Clamp a proposed selection to grades and counts the seller holds."""
    normalized = pricing.normalize(selection)
    if normalized is None:
        return None
    grades = pricing.grade_map(ctx.item)
    capped = [
        {"grade": e["grade"], "quantity": min(e["quantity"], grades[e["grade"]]["count"])}
        for e in normalized
        if e["grade"] in grades
    ]
    capped = [e for e in capped if e["quantity"] > 0]
    return capped or None


def firm_price_reply(ctx: NegotiationContext) -> GuardedDecision:
    """Hold-firm response for non-negotiable listings offered below the price."""
    item = ctx.item
    selection = pricing.normalize(ctx.negotiation.current_selection)
    if selection is None:
        quote = f"£{item.bundle_price} for the full bundle"
    else:
        asking = pricing.selection_asking(item, selection)
        quote = f"£{asking} for {pricing.describe_selection(selection)}"
    return GuardedDecision(
        decision=AgentDecision(
            action="chat",
            price=None,
            message=_pick(FIRM_PRICE, quote=quote, condition=item.condition, brand=item.brand),
        ),
        voice_note=(
            f"this listing is not negotiable, so you politely hold firm at "
            f"{quote}, delivered — no discount"
        ),
    )


def fallback_reply() -> AgentDecision:
    """Safe response when the LLM call or parsing fails; keeps the demo alive."""
    return AgentDecision(action="chat", price=None, message=_pick(FALLBACK))


def apply_guardrails(decision: AgentDecision, ctx: NegotiationContext) -> GuardedDecision:
    """Clamp an LLM decision to the item's haggle policy.

    Rules, in order:
    - accept without a standing offer becomes a chat asking for a number
    - accept below the flexed floor for the buyer's scope becomes a counter
    - counter selections are capped to real stock; counter prices are
      clamped to [flexed floor, asking] for that scope and never rise above
      the agent's previous counter on the same scope
    - a counter is converted to an accept when the buyer's valid standing
      offer already meets the clamped price on the same scope

    Whenever a rule changes the action, price, or scope, the LLM's original
    message no longer matches what happens; the returned `voice_note` flags
    it for rewording.
    """
    item = ctx.item
    offer = ctx.negotiation.current_offer
    buyer_scope = pricing.normalize(ctx.negotiation.current_selection)
    prev = previous_counter(ctx)

    if decision.action == "accept":
        if offer is None:
            return GuardedDecision(
                decision=AgentDecision(action="chat", price=None, message=_pick(ASK_FOR_NUMBER)),
                voice_note=(
                    "the buyer has not put a concrete price on the table yet, "
                    "so you ask what number they have in mind"
                ),
            )
        floor = pricing.selection_floor(item, buyer_scope)
        if offer < pricing.flex_floor(floor):
            asking = pricing.selection_asking(item, buyer_scope)
            ceiling = min(asking, prev[0]) if prev and prev[1] == buyer_scope else asking
            counter = max(floor, _to_money((offer + ceiling) / 2))
            scope_text = pricing.describe_selection(buyer_scope)
            return GuardedDecision(
                decision=AgentDecision(
                    action="counter",
                    price=float(counter),
                    selection=None,
                    message=_pick(BELOW_FLOOR_COUNTER, price=counter, scope=scope_text),
                ),
                voice_note=(
                    f"the buyer's £{offer} for {scope_text} is lower than you "
                    f"can go, so you counter at £{counter}"
                ),
            )
        return GuardedDecision(decision)

    if decision.action == "counter":
        raw_selection = [e.model_dump() for e in decision.selection] if decision.selection else None
        proposed_scope = pricing.normalize(raw_selection)
        scope = _cap_selection(ctx, raw_selection) or buyer_scope
        floor = pricing.selection_floor(item, scope)
        hard_floor = pricing.flex_floor(floor)
        asking = pricing.selection_asking(item, scope)
        ceiling = min(asking, prev[0]) if prev and prev[1] == scope else asking

        proposed_price = _to_money(decision.price) if decision.price is not None else None
        price = max(hard_floor, min(proposed_price or ceiling, ceiling))
        if offer is not None and scope == buyer_scope and offer >= hard_floor and offer >= price:
            return GuardedDecision(
                decision=AgentDecision(
                    action="accept",
                    price=None,
                    selection=None,
                    message=_pick(ACCEPT_OFFER, offer=offer),
                ),
                voice_note=(
                    f"the buyer's standing offer of £{offer} for "
                    f"{pricing.describe_selection(buyer_scope)} meets your number, "
                    f"so you accept it and close the deal"
                ),
            )
        counter_selection = None if scope == buyer_scope else scope
        clamped = price != proposed_price or (
            proposed_scope is not None and scope != proposed_scope
        )
        return GuardedDecision(
            decision=AgentDecision(
                action="counter",
                price=float(price),
                selection=counter_selection,
                message=decision.message,
            ),
            voice_note=(
                f"you counter at £{price} for "
                f"{pricing.describe_selection(scope)} (your wording must quote "
                f"exactly this price and scope)"
                if clamped
                else None
            ),
        )

    return GuardedDecision(decision)
