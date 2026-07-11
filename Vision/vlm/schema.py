"""Structured garment metadata extracted from a product crop."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class GarmentAttributes(BaseModel):
    """Catalog-oriented attributes for one isolated garment image."""

    category: str = Field(description="Primary type, e.g. jacket, coat, hoodie, dress")
    subcategory: str | None = Field(
        default=None, description="Finer type if clear, e.g. softshell, puffer, blazer"
    )
    brand: str | None = Field(default=None, description="Visible brand if readable")
    color_primary: str = Field(description="Main color in plain English")
    color_secondary: list[str] = Field(
        default_factory=list, description="Secondary colors if any"
    )
    pattern: str = Field(
        default="solid",
        description="solid, striped, checked, logo_print, camouflage, other",
    )
    material_guess: str | None = Field(
        default=None, description="Best guess from appearance, e.g. denim, cotton, synthetic"
    )
    gender_style: Literal["mens", "womens", "unisex", "kids", "unknown"] = "unknown"
    visible_text: list[str] = Field(
        default_factory=list, description="Readable text/logos on the garment"
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


class CropListing(BaseModel):
    """One crop image plus VLM attributes."""

    crop_path: str
    attributes: GarmentAttributes
    model: str
    error: str | None = None
