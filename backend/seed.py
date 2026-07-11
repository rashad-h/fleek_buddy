"""Seed the marketplace with a curated demo catalogue.

Run before a demo (`make seed`). Wipes messages, negotiations and items,
then inserts the bundles below, so re-runs always give a clean slate.

Prices are calibrated against real Fleek listings (July 2026) and are
delivered prices: price_per_piece x piece_count = bundle_price, shipping
included.

Haggle metadata convention: `buying_price` is what the seller paid,
`lowest_bundle_price` is the floor the agent defends (policy allows a small
flex below it to close a deal). The per-grade breakdown in `grades` is
seller-confidential: counts are allocated from the condition's grade mix
(AB = 70/30, BC = 60/40, ABC = 30/40/30) and per-grade prices sum back to
the bundle price.
"""

import asyncio
from decimal import Decimal
from typing import TypedDict

from sqlalchemy import text

from app.db import SessionLocal
from app.models import GradeInfo, Item

TWO_PLACES = Decimal("0.01")

# Grading allocation for mixed ratios.
GRADE_RATIOS: dict[str, dict[str, Decimal]] = {
    "A": {"A": Decimal("1.00")},
    "AB": {"A": Decimal("0.70"), "B": Decimal("0.30")},
    "B": {"B": Decimal("1.00")},
    "BC": {"B": Decimal("0.60"), "C": Decimal("0.40")},
    "ABC": {"A": Decimal("0.30"), "B": Decimal("0.40"), "C": Decimal("0.30")},
}

# Relative per-piece value of each grade within one bundle.
GRADE_MULTIPLIERS: dict[str, Decimal] = {
    "A": Decimal("1.20"),
    "B": Decimal("0.95"),
    "C": Decimal("0.70"),
}

GRADE_NOTES: dict[str, str] = {
    "A": "clean, minimal wear, best resale pieces",
    "B": "light wear, small marks, solid sellers",
    "C": "visible flaws or repairs, priced to clear",
}


class BundleSeed(TypedDict):
    """Raw values for one seeded wholesale bundle."""

    title: str
    brand: str
    vendor_name: str
    description: str
    category: str
    condition: str
    grade_mix: str
    sizes: str
    piece_count: int
    price_per_piece: str
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
        # Reference listing: joinfleek.com "Under Armour And Adidas Sexy Shorts".
        "title": "Under Armour Sexy Shorts",
        "brand": "Under Armour",
        "vendor_name": "Past Perfect Co",
        "description": (
            "Vintage Under Armour sport shorts, bold colours and prints. "
            "Mixed A/B grade as pictured; ask in chat for the exact grade "
            "split, pictures of individual pieces on request. Great resale "
            "margins for summer stock."
        ),
        "category": "Womenswear > Shorts",
        "condition": "AB Grade Vintage",
        "grade_mix": "AB",
        "sizes": "26-38",
        "piece_count": 45,
        "price_per_piece": "2.67",
        "original_price": "189.90",
        "discount_percent": 36,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/under-armour-sexy-shorts.jpg",
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
            "swooshes. Full A/B/C grade mix so there is stock for every "
            "price point; grade breakdown shared in chat. High-volume "
            "staple that sells itself."
        ),
        "category": "Menswear > T-Shirts",
        "condition": "ABC Grade Vintage",
        "grade_mix": "ABC",
        "sizes": "S-XXL",
        "piece_count": 40,
        "price_per_piece": "4.75",
        "original_price": "245.00",
        "discount_percent": 22,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/nike-vintage-tees.jpg",
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
            "Classic three-stripe track jackets, 80s-00s mix. Strong "
            "colours, all zips checked. Mixed A/B grade; pictures of "
            "specific jackets available on request."
        ),
        "category": "Menswear > Jackets",
        "condition": "AB Grade Vintage",
        "grade_mix": "AB",
        "sizes": "S-XL",
        "piece_count": 18,
        "price_per_piece": "11.50",
        "original_price": None,
        "discount_percent": None,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/adidas-track-jackets.jpg",
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
            "Rugged Carhartt chore coats and detroit jackets. Honest "
            "workwear wear, B/C grade mix priced accordingly - the C pieces "
            "are ideal for rework. Big stock ready to move."
        ),
        "category": "Menswear > Jackets",
        "condition": "BC Grade Workwear",
        "grade_mix": "BC",
        "sizes": "M-XXL",
        "piece_count": 25,
        "price_per_piece": "28.50",
        "original_price": "950.00",
        "discount_percent": 25,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/carhartt-work-jackets.jpg",
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
            "Small pony logos, all seasons. Straight A grade - every piece "
            "checked, pictures on request."
        ),
        "category": "Menswear > Polos",
        "condition": "A Grade Vintage",
        "grade_mix": "A",
        "sizes": "S-XL",
        "piece_count": 15,
        "price_per_piece": "9.00",
        "original_price": None,
        "discount_percent": None,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/ralph-lauren-polos.jpg",
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
            "Iconic 501s in medium and dark washes, waist sizes marked on "
            "every pair. Mixed A/B grade - ask for the split and pictures "
            "of specific pairs in chat."
        ),
        "category": "Unisex > Jeans",
        "condition": "AB Grade Vintage",
        "grade_mix": "AB",
        "sizes": "W28-W38",
        "piece_count": 20,
        "price_per_piece": "16.55",
        "original_price": None,
        "discount_percent": None,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/levis-501-jeans.jpg",
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
            "Premium TNF fleeces and zip-ups, straight A grade. Scarce "
            "stock, prices firm - these never sit for long."
        ),
        "category": "Unisex > Fleeces",
        "condition": "A Grade Vintage",
        "grade_mix": "A",
        "sizes": "S-XL",
        "piece_count": 20,
        "price_per_piece": "15.75",
        "original_price": None,
        "discount_percent": None,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/north-face-fleeces.jpg",
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
            "cotton, muted tones. Full A/B/C grade mix - happy to break "
            "down the grades and send pictures in chat. Winter best-seller."
        ),
        "category": "Unisex > Hoodies",
        "condition": "ABC Grade Vintage",
        "grade_mix": "ABC",
        "sizes": "M-XXL",
        "piece_count": 28,
        "price_per_piece": "13.50",
        "original_price": "472.50",
        "discount_percent": 20,
        "shipping_days_min": 20,
        "shipping_days_max": 27,
        "image_url": "/products/champion-hoodies.jpg",
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
            "90s Tommy crewnecks and quarter-zips with flag logos and "
            "colour-block knits. Mixed A/B grade, clean condition overall; "
            "grade split available in chat."
        ),
        "category": "Menswear > Sweatshirts",
        "condition": "AB Grade Vintage",
        "grade_mix": "AB",
        "sizes": "S-XL",
        "piece_count": 22,
        "price_per_piece": "15.35",
        "original_price": None,
        "discount_percent": None,
        "shipping_days_min": 14,
        "shipping_days_max": 21,
        "image_url": "/products/tommy-hilfiger-crewnecks.jpg",
        "negotiable": True,
        "high_quantity": False,
        "buying_ratio": "0.51",
        "floor_ratio": "0.83",
    },
]


def allocate_counts(total: int, ratios: dict[str, Decimal]) -> dict[str, int]:
    """Split `total` pieces across grades by ratio (largest remainder)."""
    raw = {grade: total * ratio for grade, ratio in ratios.items()}
    counts = {grade: int(value) for grade, value in raw.items()}
    leftover = total - sum(counts.values())
    by_remainder = sorted(raw, key=lambda g: raw[g] - counts[g], reverse=True)
    for grade in by_remainder[:leftover]:
        counts[grade] += 1
    return counts


def build_grades(seed: BundleSeed, bundle: Decimal, floor_ratio: Decimal) -> list[GradeInfo]:
    """Derive the confidential per-grade breakdown.

    Per-grade delivered prices follow the grade multipliers, normalised so
    they sum back to the bundle price; floors apply the bundle's floor ratio
    per piece, so a partial selection's floor is the sum of its pieces.
    """
    counts = allocate_counts(seed["piece_count"], GRADE_RATIOS[seed["grade_mix"]])
    weight = sum(count * GRADE_MULTIPLIERS[grade] for grade, count in counts.items())
    base = bundle / weight
    grades: list[GradeInfo] = []
    for grade, count in counts.items():
        price = (base * GRADE_MULTIPLIERS[grade]).quantize(TWO_PLACES)
        floor = (price * floor_ratio).quantize(TWO_PLACES)
        grades.append(
            {
                "grade": grade,
                "count": count,
                "price_per_piece": str(price),
                "floor_per_piece": str(floor),
                "note": GRADE_NOTES[grade],
            }
        )
    return grades


def build_item(seed: BundleSeed) -> Item:
    """Derive bundle, haggle and grade prices, then build the ORM row."""
    price_per_piece = Decimal(seed["price_per_piece"])
    pieces = seed["piece_count"]
    bundle = (price_per_piece * pieces).quantize(TWO_PLACES)
    floor_ratio = Decimal(seed["floor_ratio"])
    floor = (bundle * floor_ratio).quantize(TWO_PLACES)
    return Item(
        title=seed["title"],
        brand=seed["brand"],
        vendor_name=seed["vendor_name"],
        description=seed["description"],
        category=seed["category"],
        condition=seed["condition"],
        sizes=seed["sizes"],
        piece_count=pieces,
        price_per_piece=price_per_piece,
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
        grades=build_grades(seed, bundle, floor_ratio),
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
