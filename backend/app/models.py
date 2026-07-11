from datetime import datetime
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import ForeignKey, Index, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class GradeInfo(TypedDict):
    """Seller-confidential stock breakdown for one grade within a bundle.

    Prices are delivered (shipping included) so a partial selection's asking
    and floor prices sum directly from these. Money is stored as strings to
    keep JSON exact; convert with Decimal when computing.
    """

    grade: str
    count: int
    price_per_piece: str
    floor_per_piece: str
    note: str


class SelectionEntry(TypedDict):
    """One line of a partial offer: how many pieces of one grade."""

    grade: str
    quantity: int


class VisionSignals(TypedDict):
    """Seller-confidential photo signals for the negotiator.

    Aggregated from per-garment VLM listings at publish. Never expose via
    the public Item API.
    """

    suggested_stance: str
    defect_severity: str
    defects_visible: list[str]
    talking_points: list[str]
    buyer_objection_risks: list[str]
    needs_review: bool


class Base(DeclarativeBase):
    pass


class Item(Base):
    """A wholesale clothing bundle listed on the marketplace.

    `buying_price`, `lowest_bundle_price`, `lowest_price_per_piece`,
    `grades`, and `vision_signals` are the seller's confidential haggle
    metadata: they drive the negotiation agent and must never be exposed
    through the public API.
    """

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]
    brand: Mapped[str]
    vendor_name: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str]
    condition: Mapped[str]
    sizes: Mapped[str]
    piece_count: Mapped[int]
    price_per_piece: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    bundle_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    original_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    discount_percent: Mapped[int | None] = mapped_column(default=None)
    shipping_days_min: Mapped[int]
    shipping_days_max: Mapped[int]
    is_single_brand: Mapped[bool] = mapped_column(default=True)
    image_url: Mapped[str]
    image_urls: Mapped[list[str]] = mapped_column(JSONB, default=list)

    negotiable: Mapped[bool] = mapped_column(default=True)
    high_quantity: Mapped[bool] = mapped_column(default=False)
    buying_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    lowest_bundle_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    lowest_price_per_piece: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    grades: Mapped[list[GradeInfo]] = mapped_column(JSONB, default=list)
    vision_signals: Mapped[VisionSignals | None] = mapped_column(JSONB, default=None)

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    negotiations: Mapped[list["Negotiation"]] = relationship(back_populates="item")


class Negotiation(Base):
    """One buyer's haggle over one item; locked once accepted or rejected."""

    __tablename__ = "negotiations"
    __table_args__ = (Index("ix_negotiations_item_buyer", "item_id", "buyer_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(index=True)
    status: Mapped[str] = mapped_column(default="open")
    current_offer: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    # None means the offer covers the full bundle.
    current_selection: Mapped[list[SelectionEntry] | None] = mapped_column(JSONB, default=None)
    agreed_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    item: Mapped[Item] = relationship(back_populates="negotiations")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="negotiation", order_by="Message.id"
    )


class Message(Base):
    """A single chat turn; `action` and `offer_amount` mark offer events."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    negotiation_id: Mapped[int] = mapped_column(ForeignKey("negotiations.id"), index=True)
    role: Mapped[str]
    content: Mapped[str] = mapped_column(Text)
    offer_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), default=None)
    offer_selection: Mapped[list[SelectionEntry] | None] = mapped_column(JSONB, default=None)
    action: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    negotiation: Mapped[Negotiation] = relationship(back_populates="messages")
