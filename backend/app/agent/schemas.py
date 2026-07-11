from typing import Literal

from pydantic import BaseModel, Field

AgentAction = Literal["counter", "accept", "reject", "chat"]


class AgentDecision(BaseModel):
    """Structured verdict returned by the LLM for one negotiation turn.

    `price` is the counter-offer bundle price and only meaningful when
    `action == "counter"`. `message` is what the seller says to the buyer.
    """

    action: AgentAction
    price: float | None = Field(default=None, gt=0)
    message: str
