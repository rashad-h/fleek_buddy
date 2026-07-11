"""Merchant cataloging API schemas."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

JobStatus = Literal[
    "queued",
    "extracting",
    "describing",
    "summarizing",
    "complete",
    "error",
]
ItemStatus = Literal["pending", "analyzing", "complete", "error"]


class GarmentAttributesRead(BaseModel):
    category: str
    subcategory: str | None = None
    brand: str | None = None
    color_primary: str
    material_guess: str = "unknown"
    condition_visible: str
    short_title: str
    description: str
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool


class MerchantItemRead(BaseModel):
    index: int
    filename: str
    image_url: str
    status: ItemStatus
    attributes: GarmentAttributesRead | None = None
    error: str | None = None


class BundleSummary(BaseModel):
    """One wholesale listing synthesized from all per-garment Gemini analyses."""

    short_title: str = Field(description="Bundle headline for the marketplace card")
    description: str = Field(description="2-4 sentence wholesale listing body")
    brands: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    piece_count: int = Field(ge=1, description="Garments in the lot")
    condition_overall: str = Field(description="e.g. AB Grade Vintage")
    highlights: list[str] = Field(default_factory=list, max_length=4)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_review: bool = False


class MerchantJobCreateResponse(BaseModel):
    job_id: str


class MerchantJobRead(BaseModel):
    job_id: str
    status: JobStatus
    message: str
    items: list[MerchantItemRead]
    summary: BundleSummary | None = None
    error: str | None = None
    published_item_ids: list[int] = Field(default_factory=list)


class MerchantPublishResponse(BaseModel):
    job_id: str
    item_ids: list[int]
    count: int
