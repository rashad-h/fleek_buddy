"""Shared track interface so backends (SAM 3 / Grounded SAM 2) stay swappable."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class GarmentTrack:
    """One garment observation on one frame."""

    item_id: int
    frame_index: int
    bounding_box: list[float]  # XYXY absolute pixels
    confidence: float
    category: str
    mask: Any | None = None  # optional torch/np mask; omit from JSON dumps

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("mask", None)
        return data
