"""Build one wholesale bundle summary from per-item VLM rows.

Primary path is local synthesis (instant). An optional Gemini polish runs under a
hard wall-clock timeout; LiteLLM's own timeout often fails to fire for Gemini
("Connection timed out after None seconds"), so we never block the pipeline on it.
"""

from __future__ import annotations

import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path
from statistics import mean

import litellm
from pydantic import ValidationError

from app.merchant.env import vlm_subprocess_env
from app.merchant.schemas import BundleSummary

SUMMARY_MODEL = "gemini/gemini-3.5-flash"
# Hard wall-clock for the optional polish call. Keep short so the UI moves on.
GEMINI_WALL_CLOCK_S = 20
# Prefer local-only unless MERCHANT_SUMMARY_LLM=1 (Gemini often hangs after parallel VLM).
USE_GEMINI_POLISH = os.getenv("MERCHANT_SUMMARY_LLM", "").strip() in {"1", "true", "yes"}

SYSTEM_PROMPT = """\
You write one wholesale marketplace listing for a supplier haul video.
Synthesize the garment analyses into a single bundle listing.
Use only the provided data. Reply with one JSON object only, no markdown.
"""

JSON_SHAPE = """\
{
  "short_title": "string",
  "description": "string",
  "brands": ["string"],
  "categories": ["string"],
  "materials": ["string"],
  "piece_count": 1,
  "condition_overall": "string",
  "highlights": ["string"],
  "confidence": 0.0,
  "needs_review": false
}
"""


def _successful_item_payloads(listings_path: Path) -> list[dict]:
    if not listings_path.is_file():
        return []
    try:
        payload = json.loads(listings_path.read_text())
    except json.JSONDecodeError:
        return []
    rows = payload.get("listings") or []
    items: list[dict] = []
    for row in rows:
        if row.get("error"):
            continue
        attrs = row.get("attributes") or {}
        if not attrs.get("short_title"):
            continue
        items.append(
            {
                "filename": Path(str(row.get("crop_path") or "")).name,
                "short_title": attrs.get("short_title"),
                "category": attrs.get("category"),
                "subcategory": attrs.get("subcategory"),
                "brand": attrs.get("brand"),
                "color_primary": attrs.get("color_primary"),
                "material_guess": attrs.get("material_guess"),
                "condition_visible": attrs.get("condition_visible"),
                "description": attrs.get("description"),
                "needs_review": attrs.get("needs_review"),
                "confidence": attrs.get("confidence"),
            }
        )
    return items


def _parse_summary(raw: str) -> BundleSummary:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return BundleSummary.model_validate_json(text)
    except ValidationError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return BundleSummary.model_validate_json(match.group(0))


def _compact_items(items: list[dict]) -> list[dict]:
    compact: list[dict] = []
    for item in items:
        compact.append(
            {
                "title": item.get("short_title"),
                "brand": item.get("brand"),
                "category": item.get("category"),
                "subcategory": item.get("subcategory"),
                "color": item.get("color_primary"),
                "material": item.get("material_guess"),
                "condition": item.get("condition_visible"),
                "needs_review": item.get("needs_review"),
            }
        )
    return compact


def _clean_label(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"unknown", "null", "none", "n/a", "na"}:
        return None
    return text


def _uniq(values: list[object | None]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = _clean_label(value)
        if not label:
            continue
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(label)
    return out


def _local_summary(items: list[dict]) -> BundleSummary:
    """Deterministic bundle card from per-garment attributes. No network."""
    n = len(items)
    brands = _uniq([item.get("brand") for item in items])
    categories = _uniq([item.get("category") for item in items])
    materials = _uniq([item.get("material_guess") for item in items])
    conditions = _uniq([item.get("condition_visible") for item in items])
    colors = _uniq([item.get("color_primary") for item in items])

    if len(brands) == 1:
        brand_bit = brands[0]
    elif 2 <= len(brands) <= 3:
        brand_bit = " & ".join(brands)
    elif brands:
        brand_bit = f"{brands[0]}+ Mix"
    else:
        brand_bit = "Mixed Brand"

    if len(categories) == 1:
        cat_bit = categories[0]
    elif categories:
        cat_bit = "Apparel"
    else:
        cat_bit = "Garment"

    short_title = f"{brand_bit} {cat_bit} Bundle"

    cat_phrase = ", ".join(categories[:4]) if categories else "assorted garments"
    brand_phrase = (
        f" Brands include {', '.join(brands[:5])}."
        if brands
        else " Mixed / unbranded pieces."
    )
    material_phrase = (
        f" Materials lean {', '.join(materials[:4])}."
        if materials
        else ""
    )
    condition_phrase = (
        f" Visible condition: {', '.join(conditions[:3])}."
        if conditions
        else ""
    )
    description = (
        f"Wholesale lot of {n} {cat_phrase} pulled from a supplier haul video."
        f"{brand_phrase}{material_phrase}{condition_phrase}"
    )

    condition_overall = conditions[0] if len(conditions) == 1 else (
        " / ".join(conditions[:2]) if conditions else "As pictured"
    )

    highlights: list[str] = [f"{n} pieces in lot"]
    if brands:
        highlights.append(
            f"{len(brands)} brand{'s' if len(brands) != 1 else ''}: "
            + ", ".join(brands[:3])
        )
    if categories:
        highlights.append(", ".join(categories[:3]))
    if colors:
        highlights.append(f"Colors: {', '.join(colors[:3])}")
    highlights = highlights[:4]

    confidences = [
        float(c)
        for item in items
        if (c := item.get("confidence")) is not None
    ]
    confidence = round(mean(confidences), 3) if confidences else 0.5
    needs_review = sum(1 for item in items if item.get("needs_review")) >= max(1, n // 2)

    return BundleSummary(
        short_title=short_title[:120],
        description=description.strip(),
        brands=brands,
        categories=categories,
        materials=materials,
        piece_count=n,
        condition_overall=condition_overall[:80],
        highlights=highlights,
        confidence=min(1.0, max(0.0, confidence)),
        needs_review=needs_review,
    )


def _gemini_summary(items: list[dict]) -> BundleSummary:
    env = vlm_subprocess_env()
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        value = env.get(key)
        if value:
            os.environ[key] = value
    if not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")):
        raise RuntimeError("Missing GEMINI_API_KEY for bundle summary")

    user_payload = {
        "piece_count_hint": len(items),
        "items": _compact_items(items),
    }
    # Single user message — Gemini via LiteLLM is flaky with separate system roles.
    messages = [
        {
            "role": "user",
            "content": (
                f"{SYSTEM_PROMPT}\n"
                f"JSON shape:\n{JSON_SHAPE}\n"
                f"Data:\n{json.dumps(user_payload, separators=(',', ':'))}"
            ),
        },
    ]
    response = litellm.completion(
        model=SUMMARY_MODEL,
        messages=messages,
        timeout=GEMINI_WALL_CLOCK_S,
        request_timeout=GEMINI_WALL_CLOCK_S,
        num_retries=0,
    )
    raw = response.choices[0].message.content or ""
    summary = _parse_summary(raw)
    summary.piece_count = len(items)
    return summary


def summarize_listings(listings_path: Path, *, out_path: Path) -> BundleSummary:
    """Item analyses JSON → one BundleSummary. Writes summary.json."""
    log_path = out_path.with_name("summary.log")
    items = _successful_item_payloads(listings_path)
    if not items:
        raise RuntimeError("No successful item analyses to summarize")

    local = _local_summary(items)
    log_lines = [
        f"items={len(items)}",
        f"local_title={local.short_title}",
        f"gemini_polish={USE_GEMINI_POLISH}",
        f"wall_clock_s={GEMINI_WALL_CLOCK_S}",
    ]

    summary = local
    if USE_GEMINI_POLISH:
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_gemini_summary, items)
                summary = future.result(timeout=GEMINI_WALL_CLOCK_S)
            log_lines.append("mode=gemini")
            log_lines.append(f"gemini_title={summary.short_title}")
        except FuturesTimeout:
            log_lines.append("mode=local-fallback")
            log_lines.append(f"error=wall_clock_timeout_{GEMINI_WALL_CLOCK_S}s")
            summary = local
        except Exception as exc:
            log_lines.append("mode=local-fallback")
            log_lines.append(f"error={type(exc).__name__}: {exc}")
            summary = local
    else:
        log_lines.append("mode=local")

    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    out_path.write_text(json.dumps(summary.model_dump(), indent=2))
    return summary
