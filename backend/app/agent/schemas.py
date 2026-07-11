from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import OfferSelection

AgentAction = Literal["counter", "accept", "reject", "chat"]


class AgentDecision(BaseModel):
    """Structured verdict returned by the LLM for one negotiation turn.

    `price` is the counter-offer delivered price and only meaningful when
    `action == "counter"`. `selection` scopes that price to specific grade
    quantities (None = the buyer's current scope / full bundle) and lets the
    seller counter with different quantities than the buyer asked for.
    `buyer_price` is the price the buyer named in their latest message when
    it differs from the standing offer; it only replaces the standing offer
    after `policy.adopt_text_offer` verifies the number appears verbatim in
    that message. `message` is what the seller says to the buyer.
    """

    action: AgentAction
    price: float | None = Field(default=None, gt=0)
    buyer_price: float | None = Field(default=None, gt=0)
    selection: list[OfferSelection] | None = None
    message: str
