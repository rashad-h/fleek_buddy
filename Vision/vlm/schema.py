"""Structured garment metadata extracted from a product crop/frame."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


BrandTier = Literal["luxury", "premium", "mid", "fast_fashion", "unknown"]
DefectSeverity = Literal["none", "minor", "major", "unknown"]
SuggestedStance = Literal["firm", "balanced", "flexible"]


class GarmentAttributes(BaseModel):
    """Catalog + lean negotiation signals from one garment image.

    Kept small on purpose: extra fields raise cost and Gemini gets unreliable.
    """

    category: str = Field(description="Primary type, e.g. jacket, coat, hoodie, vest")
    subcategory: str | None = Field(
        default=None, description="Finer type if clear, e.g. softshell, puffer"
    )
    brand: str | None = Field(default=None, description="Visible brand if readable")
    brand_tier: BrandTier = Field(
        default="unknown",
        description="Resale tier of the brand if known; unknown if brand unclear",
    )
    color_primary: str = Field(description="Main color in plain English")
    color_secondary: list[str] = Field(
        default_factory=list, description="Secondary colors if any"
    )
    pattern: str = Field(
        default="solid",
        description="solid, striped, checked, logo_print, camouflage, other",
    )
    visible_text: list[str] = Field(
        default_factory=list, description="Readable logos/text on the garment"
    )
    condition_visible: Literal[
        "new_with_tags",
        "new_without_tags",
        "used_excellent",
        "used_good",
        "used_fair",
        "unknown",
    ] = "unknown"
    defects_visible: list[str] = Field(
        default_factory=list,
        description="Visible issues only, e.g. stain, hole, missing_button",
    )
    defect_severity: DefectSeverity = Field(
        default="unknown",
        description="none if clean; minor/major from visible defects only",
    )
    talking_points: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 short seller talking points grounded in the image",
    )
    buyer_objection_risks: list[str] = Field(
        default_factory=list,
        max_length=3,
        description="Up to 3 likely buyer objections from what is visible/missing",
    )
    short_title: str = Field(
        description="Short listing title, e.g. 'Purple The North Face softshell jacket'"
    )
    description: str = Field(
        description="1-2 sentence marketplace-style description from what is visible"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Model confidence in the overall extraction"
    )
    needs_review: bool = Field(
        description="True if crop is blurry, occluded, or attributes are uncertain"
    )


def derive_suggested_stance(attrs: GarmentAttributes) -> SuggestedStance:
    """Heuristic stance for the seller agent — not asked from the VLM."""
    if attrs.defect_severity == "major" or attrs.needs_review or attrs.confidence < 0.55:
        return "flexible"
    if attrs.brand_tier in {"luxury", "premium"} and attrs.defect_severity == "none":
        return "firm"
    return "balanced"


class CropListing(BaseModel):
    """One image plus VLM attributes and derived negotiation stance."""

    crop_path: str
    attributes: GarmentAttributes
    suggested_stance: SuggestedStance
    model: str
    error: str | None = None
