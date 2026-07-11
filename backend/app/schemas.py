from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

NegotiationStatus = Literal["open", "accepted", "rejected"]
MessageRole = Literal["buyer", "agent", "system"]
MessageAction = Literal["offer", "counter", "accept", "reject", "chat"]


class OfferSelection(BaseModel):
    """One line of a partial offer: how many pieces of one grade."""

    grade: str
    quantity: int = Field(gt=0)


class ItemRead(BaseModel):
    """Public view of an item. Seller secrets (buying price, floor prices,
    the per-grade stock breakdown) are deliberately absent."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    brand: str
    vendor_name: str
    description: str
    category: str
    condition: str
    sizes: str
    piece_count: int
    price_per_piece: float
    bundle_price: float
    original_price: float | None
    discount_percent: int | None
    shipping_days_min: int
    shipping_days_max: int
    is_single_brand: bool
    image_url: str
    negotiable: bool
    high_quantity: bool
    created_at: datetime


class NegotiationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    buyer_id: str
    status: NegotiationStatus
    current_offer: float | None
    current_selection: list[OfferSelection] | None
    agreed_price: float | None
    created_at: datetime
    updated_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    negotiation_id: int
    role: MessageRole
    content: str
    offer_amount: float | None
    offer_selection: list[OfferSelection] | None
    action: MessageAction | None
    created_at: datetime


class NegotiationDetail(NegotiationRead):
    messages: list[MessageRead]


class NegotiationCreate(BaseModel):
    """`selection` limits the offer to specific grades; None means full bundle."""

    item_id: int
    buyer_id: str
    offer_price: float = Field(gt=0)
    selection: list[OfferSelection] | None = None
    message: str | None = None


class BuyerMessage(BaseModel):
    """Content may be empty when the buyer only submits a new offer amount.

    `selection` limits a new offer to specific grades; None keeps the
    negotiation's current scope.
    """

    content: str = ""
    offer_amount: float | None = Field(default=None, gt=0)
    selection: list[OfferSelection] | None = None
