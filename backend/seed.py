"""Seed the marketplace with a curated demo catalogue.

Run before a demo (`make seed`). Wipes messages, negotiations and items,
then inserts the bundles below, so re-runs always give a clean slate.

Haggle metadata convention: `buying_price` is what the seller paid,
`lowest_bundle_price` is the hard floor the agent may never go under.
"""

import asyncio
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import text

from app.db import SessionLocal
from app.models import Item


class BundleSeed(TypedDict):
    """Raw values for one seeded wholesale bundle."""

    title: str
    brand: str
    vendor_name: str
    description: str
    category: str
    condition: str
    sizes: str
    piece_count: int
    price_per_piece: str
    bundle_price: str
    original_price: str | None
    discount_percent: int | None
    shipping_days_min: int
    shipping_days_max: int
    image_url: str
    negotiable: bool
    high_quantity: bool
    buying_ratio: str
    floor_ratio: str


BUNDLES: list[BundleSeed] = [
    {
        # Reference listing: joinfleek.com "Under Armour Sexy Shorts".
        "title": "Under Armour Sexy Shorts",
        "brand": "Under Armour",
        "vendor_name": "Past Perfect Co",
        "description": (
            "AB-grade vintage Under Armour shorts, single-brand bundle. "
            "The images show the exact products that are part of the bundle. "
            "Great resale margins for summer stock."
        ),
        "category": "Womenswear > Shorts",
        "condition": "AB Grade Vintage",
        "sizes": "26-38",
        "piece_count": 23,
        # Fleek shows per-piece price excluding shipping; the bundle total includes it.
        "price_per_piece": "4.35",
        "bundle_price": "171.35",
        "original_price": "290.00",
        "discount_percent": 41,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/under-armour-sexy-shorts.svg",
        "negotiable": True,
        "high_quantity": False,
        "buying_ratio": "0.50",
        "floor_ratio": "0.80",
    },
    {
        "title": "Nike Vintage Tees Mix",
        "brand": "Nike",
        "vendor_name": "Thrift Empire",
        "description": (
            "Assorted 90s and 00s Nike tees, bold graphics and embroidered "
            "swooshes. High-volume staple that sells itself."
        ),
        "category": "Menswear > T-Shirts",
        "condition": "A Grade Vintage",
        "sizes": "S-XXL",
        "piece_count": 45,
        "price_per_piece": "5.45",
        "bundle_price": "315.00",
        "original_price": "420.00",
        "discount_percent": 25,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/nike-vintage-tees.svg",
        "negotiable": True,
        "high_quantity": True,
        "buying_ratio": "0.48",
        "floor_ratio": "0.78",
    },
    {
        "title": "Adidas Track Jackets",
        "brand": "Adidas",
        "vendor_name": "Retro Supply",
        "description": (
            "Classic three-stripe track jackets, 80s-00s mix. Strong colours, all zips checked."
        ),
        "category": "Menswear > Jackets",
        "condition": "AB Grade Vintage",
        "sizes": "S-XL",
        "piece_count": 18,
        "price_per_piece": "15.50",
        "bundle_price": "342.00",
        "original_price": "450.00",
        "discount_percent": 24,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/adidas-track-jackets.svg",
        "negotiable": True,
        "high_quantity": False,
        "buying_ratio": "0.52",
        "floor_ratio": "0.82",
    },
    {
        "title": "Carhartt Work Jackets",
        "brand": "Carhartt",
        "vendor_name": "Workwear World",
        "description": (
            "Rugged Carhartt chore coats and detroit jackets. "
            "Honest wear, no rips. Big stock ready to move."
        ),
        "category": "Menswear > Jackets",
        "condition": "B Grade Vintage",
        "sizes": "M-XXL",
        "piece_count": 30,
        "price_per_piece": "18.40",
        "bundle_price": "690.00",
        "original_price": "920.00",
        "discount_percent": 25,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/carhartt-work-jackets.svg",
        "negotiable": True,
        "high_quantity": True,
        "buying_ratio": "0.50",
        "floor_ratio": "0.78",
    },
    {
        "title": "Ralph Lauren Polos",
        "brand": "Ralph Lauren",
        "vendor_name": "Past Perfect Co",
        "description": (
            "Timeless Polo Ralph Lauren shirts, pastel and classic tones. "
            "Small pony logos, all seasons."
        ),
        "category": "Menswear > Polos",
        "condition": "A Grade Vintage",
        "sizes": "S-XL",
        "piece_count": 25,
        "price_per_piece": "14.30",
        "bundle_price": "437.50",
        "original_price": "560.00",
        "discount_percent": 22,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/ralph-lauren-polos.svg",
        "negotiable": True,
        "high_quantity": False,
        "buying_ratio": "0.53",
        "floor_ratio": "0.84",
    },
    {
        "title": "Levi's 501 Jeans Bundle",
        "brand": "Levi's",
        "vendor_name": "Denim Dealers",
        "description": (
            "Iconic 501s in medium and dark washes. Graded for minimal wear, "
            "waist sizes marked on every pair."
        ),
        "category": "Unisex > Jeans",
        "condition": "AB Grade Vintage",
        "sizes": "W28-W38",
        "piece_count": 20,
        "price_per_piece": "22.50",
        "bundle_price": "540.00",
        "original_price": "720.00",
        "discount_percent": 25,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/levis-501-jeans.svg",
        "negotiable": True,
        "high_quantity": False,
        "buying_ratio": "0.50",
        "floor_ratio": "0.82",
    },
    {
        "title": "The North Face Fleeces",
        "brand": "The North Face",
        "vendor_name": "Summit Vintage",
        "description": (
            "Premium TNF fleeces and zip-ups. Scarce stock, prices firm - these never sit for long."
        ),
        "category": "Unisex > Fleeces",
        "condition": "A Grade Vintage",
        "sizes": "S-XL",
        "piece_count": 15,
        "price_per_piece": "29.00",
        "bundle_price": "525.00",
        "original_price": None,
        "discount_percent": None,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/north-face-fleeces.svg",
        "negotiable": False,
        "high_quantity": False,
        "buying_ratio": "0.60",
        "floor_ratio": "1.00",
    },
    {
        "title": "Champion Hoodies",
        "brand": "Champion",
        "vendor_name": "Thrift Empire",
        "description": (
            "Reverse-weave and script-logo Champion hoodies, heavyweight "
            "cotton, muted tones. Winter best-seller."
        ),
        "category": "Unisex > Hoodies",
        "condition": "AB Grade Vintage",
        "sizes": "M-XXL",
        "piece_count": 28,
        "price_per_piece": "13.60",
        "bundle_price": "476.00",
        "original_price": "640.00",
        "discount_percent": 26,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/champion-hoodies.svg",
        "negotiable": True,
        "high_quantity": True,
        "buying_ratio": "0.47",
        "floor_ratio": "0.78",
    },
    {
        "title": "Tommy Hilfiger Crewnecks",
        "brand": "Tommy Hilfiger",
        "vendor_name": "Retro Supply",
        "description": (
            "90s Tommy crewnecks with flag logos and colour-block knits. "
            "Clean condition, ready for resale."
        ),
        "category": "Menswear > Sweatshirts",
        "condition": "A Grade Vintage",
        "sizes": "S-XL",
        "piece_count": 22,
        "price_per_piece": "15.50",
        "bundle_price": "418.00",
        "original_price": "550.00",
        "discount_percent": 24,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/tommy-hilfiger-crewnecks.svg",
        "negotiable": True,
        "high_quantity": False,
        "buying_ratio": "0.51",
        "floor_ratio": "0.83",
    },
]

TWO_PLACES = Decimal("0.01")


def build_item(seed: BundleSeed) -> Item:
    """Derive per-piece and haggle prices, then build the ORM row."""
    bundle = Decimal(seed["bundle_price"])
    pieces = seed["piece_count"]
    floor = (bundle * Decimal(seed["floor_ratio"])).quantize(TWO_PLACES)
    return Item(
        title=seed["title"],
        brand=seed["brand"],
        vendor_name=seed["vendor_name"],
        description=seed["description"],
        category=seed["category"],
        condition=seed["condition"],
        sizes=seed["sizes"],
        piece_count=pieces,
        price_per_piece=Decimal(seed["price_per_piece"]),
        bundle_price=bundle,
        original_price=(Decimal(seed["original_price"]) if seed["original_price"] else None),
        discount_percent=seed["discount_percent"],
        shipping_days_min=seed["shipping_days_min"],
        shipping_days_max=seed["shipping_days_max"],
        image_url=seed["image_url"],
        negotiable=seed["negotiable"],
        high_quantity=seed["high_quantity"],
        buying_price=(bundle * Decimal(seed["buying_ratio"])).quantize(TWO_PLACES),
        lowest_bundle_price=floor,
        lowest_price_per_piece=(floor / pieces).quantize(TWO_PLACES),
    )


async def main() -> None:
    async with SessionLocal() as session:
        await session.execute(
            text("TRUNCATE messages, negotiations, items RESTART IDENTITY CASCADE")
        )
        session.add_all(build_item(seed) for seed in BUNDLES)
        await session.commit()
    print(f"Seeded {len(BUNDLES)} bundles.")


if __name__ == "__main__":
    asyncio.run(main())
