"""Build multimodal LiteLLM messages for garment crop → JSON attributes."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

SYSTEM_PROMPT = """\
You extract structured product metadata for second-hand / resale clothing listings.

The image is a full video frame from a supplier rack-pass. Focus on the
front-most garment being held up / presented to the camera.

Rules:
- Describe that primary garment only. Ignore the background rack, wall, hangers,
  and the person's hand/arm unless they obscure the item.
- Use only what is visible. Do not invent brands, sizes, prices, or defects.
- If text/logo is unreadable, set brand to null and brand_tier to unknown.
- brand_tier: luxury / premium / mid / fast_fashion / unknown (from brand only).
- defect_severity: none if no visible damage; else minor or major.
- talking_points: at most 3 short, concrete seller points from the image.
- buyer_objection_risks: at most 3 risks a buyer might raise (blur, missing size
  tag, wear, occlusion). Empty list if none.
- Prefer plain catalog language over marketing fluff.
- Set needs_review=true when the frame is blurry, heavily occluded, or you are
  unsure about category/brand/color.
- confidence is your overall certainty from 0 to 1.
- Return JSON that matches the provided schema exactly.
"""


def image_data_url(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    if mime is None:
        mime = "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def build_messages(
    image_path: Path,
    *,
    category_hint: str | None = None,
) -> list[dict]:
    hint = (
        f"Soft prior from the detector (may be wrong): category≈{category_hint}.\n"
        if category_hint
        else ""
    )
    user_text = (
        f"{hint}"
        "Describe the front-most garment for a wholesale listing and negotiation "
        "context. Fill every schema field; use null/empty lists when unknown."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_text},
                {
                    "type": "image_url",
                    "image_url": {"url": image_data_url(image_path)},
                },
            ],
        },
    ]
