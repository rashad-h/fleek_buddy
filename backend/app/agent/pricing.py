"""Selection-aware price math shared by the agent's context and guardrails.

A "selection" is a list of {grade, quantity} lines limiting an offer to part
of the bundle; None always means the full bundle. All prices are delivered
(shipping included), so a selection's asking/floor is just the sum of its
per-grade per-piece prices.
"""

from decimal import Decimal

from app.models import GradeInfo, Item, SelectionEntry

TWO_PLACES = Decimal("0.01")

# The floor is a guide, not a cliff: the seller may close slightly under it
# (e.g. £135 against a £137 floor) to land on a cleaner number.
FLOOR_FLEX = Decimal("0.02")


def grade_map(item: Item) -> dict[str, GradeInfo]:
    return {g["grade"].upper(): g for g in item.grades}


def normalize(selection: list[SelectionEntry] | None) -> list[SelectionEntry] | None:
    """Canonical form for comparing selections: uppercased, sorted, merged."""
    if not selection:
        return None
    merged: dict[str, int] = {}
    for entry in selection:
        grade = entry["grade"].upper()
        merged[grade] = merged.get(grade, 0) + int(entry["quantity"])
    return [{"grade": g, "quantity": q} for g, q in sorted(merged.items())]


def selection_pieces(selection: list[SelectionEntry] | None) -> int | None:
    if not selection:
        return None
    return sum(int(entry["quantity"]) for entry in selection)


def _sum_for(item: Item, selection: list[SelectionEntry], key: str) -> Decimal:
    grades = grade_map(item)
    total = Decimal("0")
    for entry in selection:
        quantity = int(entry["quantity"])
        info = grades.get(entry["grade"].upper())
        if info is not None:
            # More pieces than the seller holds can't make the deal bigger.
            quantity = min(quantity, info["count"])
            total += quantity * Decimal(info[key])
        else:
            per_piece = (
                item.lowest_price_per_piece if key == "floor_per_piece" else item.price_per_piece
            )
            total += quantity * per_piece
    return total.quantize(TWO_PLACES)


def selection_asking(item: Item, selection: list[SelectionEntry] | None) -> Decimal:
    """Delivered asking price for the selection (bundle price when None)."""
    if not selection:
        return item.bundle_price
    return min(_sum_for(item, selection, "price_per_piece"), item.bundle_price)


def selection_floor(item: Item, selection: list[SelectionEntry] | None) -> Decimal:
    """The seller's floor for the selection (bundle floor when None)."""
    if not selection:
        return item.lowest_bundle_price
    return min(_sum_for(item, selection, "floor_per_piece"), item.lowest_bundle_price)


def flex_floor(floor: Decimal) -> Decimal:
    """The hard limit code enforces: floor minus the small closing flex."""
    return (floor * (Decimal("1") - FLOOR_FLEX)).quantize(TWO_PLACES)


def describe_selection(selection: list[SelectionEntry] | None) -> str:
    if not selection:
        return "the full bundle"
    return " + ".join(f"{e['quantity']}x Grade {e['grade'].upper()}" for e in selection)
