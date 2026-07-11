"""Publish one marketplace bundle per merchant video job."""

from __future__ import annotations

import json
import shutil
from decimal import Decimal
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.merchant.jobs import JobState
from app.merchant.paths import repo_root
from app.merchant.schemas import BundleSummary
from app.merchant.vision_signals import aggregate_vision_signals
from app.models import GradeInfo, Item

TWO_PLACES = Decimal("0.01")
VENDOR_NAME = "Video Catalog"

# Per-piece demo pricing for video haul bundles (shipping included).
ASK_PER_PIECE = Decimal("8.50")
FLOOR_PER_PIECE = Decimal("5.00")
BUYING_PER_PIECE = Decimal("3.50")


def _load_summary(job: JobState) -> BundleSummary:
    path = job.root / "summary.json"
    if not path.is_file():
        raise FileNotFoundError("Bundle summary missing; wait for summarizing to finish")
    return BundleSummary.model_validate_json(path.read_text())


def _cover_filename(job: JobState) -> str:
    for item in job.items:
        if item.status == "complete" and (job.frames_dir / item.filename).is_file():
            return item.filename
    raise FileNotFoundError("No frame available for cover image")


def _public_merchant_dir(job_id: str) -> Path:
    return repo_root() / "ui" / "public" / "merchant" / job_id


def _copy_frames_for_buyer(job: JobState) -> tuple[str, list[str]]:
    """Copy extracted frames into ui/public; return cover + all public URLs."""
    dest = _public_merchant_dir(job.job_id)
    dest.mkdir(parents=True, exist_ok=True)
    cover = _cover_filename(job)
    urls: list[str] = []
    for frame in sorted(job.frames_dir.glob("item_*.jpg")):
        shutil.copy2(frame, dest / frame.name)
        urls.append(f"/merchant/{job.job_id}/{frame.name}")
    if not urls:
        raise FileNotFoundError("No frames to publish")
    cover_url = f"/merchant/{job.job_id}/{cover}"
    if cover_url in urls:
        urls = [cover_url] + [u for u in urls if u != cover_url]
    return cover_url, urls


def _grades(piece_count: int) -> list[GradeInfo]:
    a_count = max(1, round(piece_count * 0.7))
    b_count = max(0, piece_count - a_count)
    grades: list[GradeInfo] = [
        {
            "grade": "A",
            "count": a_count,
            "price_per_piece": str(ASK_PER_PIECE),
            "floor_per_piece": str(FLOOR_PER_PIECE),
            "note": "best pieces from video haul",
        }
    ]
    if b_count:
        grades.append(
            {
                "grade": "B",
                "count": b_count,
                "price_per_piece": str((ASK_PER_PIECE * Decimal("0.85")).quantize(TWO_PLACES)),
                "floor_per_piece": str((FLOOR_PER_PIECE * Decimal("0.85")).quantize(TWO_PLACES)),
                "note": "light wear from video haul",
            }
        )
    return grades


def _brand_label(summary: BundleSummary) -> str:
    if not summary.brands:
        return "Mixed"
    if len(summary.brands) == 1:
        return summary.brands[0]
    if len(summary.brands) <= 3:
        return " / ".join(summary.brands)
    return "Mixed brands"


def _category_label(summary: BundleSummary) -> str:
    if not summary.categories:
        return "Mixed > Wholesale"
    return " / ".join(summary.categories[:3])


def _full_description(summary: BundleSummary, job: JobState) -> str:
    parts = [summary.description.strip()]
    if summary.highlights:
        parts.append("Highlights: " + "; ".join(summary.highlights))
    if summary.materials:
        parts.append("Materials: " + ", ".join(summary.materials))

    lines: list[str] = []
    for item in job.items:
        if item.status != "complete" or not item.attributes:
            continue
        attrs = item.attributes
        bit = attrs.short_title
        if attrs.material_guess and attrs.material_guess != "unknown":
            bit += f" ({attrs.material_guess})"
        lines.append(f"- {bit}")
    if lines:
        parts.append("Includes:\n" + "\n".join(lines))
    return "\n\n".join(parts)


async def publish_job_to_catalogue(
    session: AsyncSession,
    job: JobState,
) -> list[int]:
    """Insert one marketplace Item for the whole video haul. Returns [item_id]."""
    summary = _load_summary(job)
    image_url, image_urls = _copy_frames_for_buyer(job)
    piece_count = max(1, summary.piece_count)
    ask = (ASK_PER_PIECE * piece_count).quantize(TWO_PLACES)
    floor = (FLOOR_PER_PIECE * piece_count).quantize(TWO_PLACES)
    buying = (BUYING_PER_PIECE * piece_count).quantize(TWO_PLACES)

    item = Item(
        title=summary.short_title,
        brand=_brand_label(summary),
        vendor_name=VENDOR_NAME,
        description=_full_description(summary, job),
        category=_category_label(summary),
        condition=summary.condition_overall or "AB Grade Vintage",
        sizes="Mixed",
        piece_count=piece_count,
        price_per_piece=ASK_PER_PIECE,
        bundle_price=ask,
        original_price=(ask * Decimal("1.35")).quantize(TWO_PLACES),
        discount_percent=26,
        shipping_days_min=7,
        shipping_days_max=14,
        is_single_brand=len(summary.brands) <= 1,
        image_url=image_url,
        image_urls=image_urls,
        negotiable=True,
        high_quantity=piece_count >= 10,
        buying_price=buying,
        lowest_bundle_price=floor,
        lowest_price_per_piece=FLOOR_PER_PIECE,
        grades=_grades(piece_count),
        vision_signals=aggregate_vision_signals(job.listings_path),
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    summary_path = job.root / "summary.json"
    if summary_path.is_file():
        payload = json.loads(summary_path.read_text())
        payload["published_item_id"] = item.id
        summary_path.write_text(json.dumps(payload, indent=2))

    return [item.id]
