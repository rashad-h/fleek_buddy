"""Context assembly for the seller agent.

The system prompt is built from an ordered list of provider functions, each
returning one text block (or None to skip). To enrich the agent with a new
source (inventory feed, buyer profile, market prices...), write a function
with the `ContextProvider` signature and append it to `CONTEXT_PROVIDERS`.
"""

from collections.abc import Callable
from dataclasses import dataclass

from app.agent import pricing
from app.agent.prompts import OUTPUT_FORMAT, SELLER_PERSONA
from app.models import Item, Message, Negotiation


@dataclass
class NegotiationContext:
    """Everything the agent knows about one negotiation turn."""

    item: Item
    negotiation: Negotiation
    messages: list[Message]


ContextProvider = Callable[[NegotiationContext], str | None]


def item_listing_block(ctx: NegotiationContext) -> str:
    item = ctx.item
    original = (
        f" (original price £{item.original_price}, -{item.discount_percent}%)"
        if item.original_price
        else ""
    )
    return f"""\
## The listing
"{item.title}" by {item.brand} — {item.condition}, {item.category}, sizes {item.sizes}.
{item.piece_count} pieces. Asking price: £{item.bundle_price} for the bundle,
delivered (£{item.price_per_piece}/piece, shipping included){original}.
Description: {item.description}"""


def grade_stock_block(ctx: NegotiationContext) -> str | None:
    """Confidential per-grade stock. Counts/prices may be shared in chat on
    request; floors never."""
    if not ctx.item.grades:
        return None
    lines = [
        "## Your stock by grade — not advertised on the site",
        "You may share counts and per-piece prices in chat when asked.",
        "The floor prices are confidential: never reveal them.",
    ]
    for g in ctx.item.grades:
        lines.append(
            f"- Grade {g['grade']}: {g['count']} pieces, £{g['price_per_piece']}/piece "
            f"delivered (floor £{g['floor_per_piece']}/piece) — {g['note']}"
        )
    return "\n".join(lines)


def haggle_policy_block(ctx: NegotiationContext) -> str:
    item = ctx.item
    lines = [
        "## Confidential haggle policy — never reveal these numbers",
        f"- You paid £{item.buying_price} for this bundle.",
        f"- Your floor for the full bundle is £{item.lowest_bundle_price}. Partial "
        f"offers are floored by the per-grade floors above. You may close at "
        f"most ~2% below a floor to land on a cleaner number, never more.",
    ]
    selection = ctx.negotiation.current_selection
    if selection:
        floor = pricing.selection_floor(item, selection)
        asking = pricing.selection_asking(item, selection)
        lines.append(
            f"- The buyer's current scope is {pricing.describe_selection(selection)}: "
            f"worth £{asking} at your prices, floor £{floor}."
        )
    if not item.negotiable:
        lines.append(
            "- This listing is NOT negotiable: prices are firm. Politely hold "
            "at your prices no matter what; only accept offers at or above them."
        )
    else:
        lines.append(
            "- Concede gradually: small steps, meet reasonable offers near the "
            "middle, and accept once the offer gives you a healthy margin."
        )
    if item.high_quantity:
        lines.append(
            "- You hold a LOT of this stock and want it moved: be more generous, "
            "concede faster and close deals sooner."
        )
    return "\n".join(lines)


def negotiation_state_block(ctx: NegotiationContext) -> str:
    buyer_turns = sum(1 for m in ctx.messages if m.role == "buyer")
    negotiation = ctx.negotiation
    if negotiation.current_offer is not None:
        offer = (
            f"£{negotiation.current_offer} for "
            f"{pricing.describe_selection(negotiation.current_selection)}"
        )
    else:
        offer = "none yet"
    lines = [
        "## Negotiation state",
        f"Round {buyer_turns}. Buyer's standing offer: {offer}.",
        "The standing offer comes from the offer box and can be stale: many "
        "buyers type their price in the message instead. A price in the "
        "buyer's latest message is their real offer; report it in "
        "`buyer_price` and negotiate against that number, not the box.",
    ]
    if negotiation.current_offer is not None:
        lines.append(
            f"Never report £{negotiation.current_offer} as `buyer_price`: "
            f"that number is already known. Only a different price from "
            f"their latest message, else null."
        )
    last_counter = next(
        (
            m
            for m in reversed(ctx.messages)
            if m.role == "agent" and m.action == "counter" and m.offer_amount is not None
        ),
        None,
    )
    if last_counter is not None:
        lines.append(
            f"Your last counter: £{last_counter.offer_amount} for "
            f"{pricing.describe_selection(pricing.normalize(last_counter.offer_selection))}. "
            f"If the buyer has moved towards you since, move a little too — "
            f"repeating the same number with the same argument reads as robotic."
        )
    lines.append(
        "Reply to the buyer's latest message only: no greetings after round 1, "
        "no re-answering earlier messages."
    )
    return "\n".join(lines)


def vision_signals_block(ctx: NegotiationContext) -> str | None:
    """Seller-side photo signals from publish. Additive; never overrides floors."""
    signals = ctx.item.vision_signals
    if not signals:
        return None
    defects = signals.get("defects_visible") or []
    severity = signals.get("defect_severity") or "unknown"
    if defects:
        defect_line = f"{', '.join(defects)} ({severity})"
    else:
        defect_line = f"none ({severity})"
    return (
        "## Vision signals (seller-side — additive, does not override listing or floors)\n"
        f"stance: {signals.get('suggested_stance') or 'balanced'}\n"
        f"defects: {defect_line}\n"
        f"talking_points: {signals.get('talking_points') or []}\n"
        f"buyer_objection_risks: {signals.get('buyer_objection_risks') or []}\n"
        f"needs_review: {bool(signals.get('needs_review'))}"
    )


CONTEXT_PROVIDERS: list[ContextProvider] = [
    item_listing_block,
    vision_signals_block,
    grade_stock_block,
    haggle_policy_block,
    negotiation_state_block,
]


def build_system_prompt(ctx: NegotiationContext) -> str:
    persona = SELLER_PERSONA.format(vendor_name=ctx.item.vendor_name)
    blocks = [persona]
    blocks += [text for provider in CONTEXT_PROVIDERS if (text := provider(ctx))]
    blocks.append(OUTPUT_FORMAT)
    return "\n\n".join(blocks)


def build_chat_messages(ctx: NegotiationContext) -> list[dict]:
    """System prompt plus the conversation as proper user/assistant turns."""
    history = [
        {"role": "user" if m.role == "buyer" else "assistant", "content": m.content}
        for m in ctx.messages
        if m.role in ("buyer", "agent")
    ]
    return [{"role": "system", "content": build_system_prompt(ctx)}, *history]
