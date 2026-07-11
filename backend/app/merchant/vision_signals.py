"""Aggregate per-garment VLM signals into one confidential bundle cheat sheet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_SEVERITY_RANK = {"unknown": 0, "none": 1, "minor": 2, "major": 3}
_STANCE_RANK = {"firm": 1, "balanced": 2, "flexible": 3}


def _str_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _worst_severity(values: list[str]) -> str:
    best = "unknown"
    best_rank = -1
    for value in values:
        rank = _SEVERITY_RANK.get(value, 0)
        if rank > best_rank:
            best = value if value in _SEVERITY_RANK else "unknown"
            best_rank = rank
    return best


def _worst_stance(values: list[str]) -> str:
    best = "balanced"
    best_rank = _STANCE_RANK[best]
    for value in values:
        rank = _STANCE_RANK.get(value)
        if rank is not None and rank > best_rank:
            best = value
            best_rank = rank
    return best


def _derive_stance(
    *,
    defect_severity: str,
    needs_review: bool,
    confidence: float,
    brand_tier: str | None,
) -> str:
    if defect_severity == "major" or needs_review or confidence < 0.55:
        return "flexible"
    if brand_tier in {"luxury", "premium"} and defect_severity == "none":
        return "firm"
    return "balanced"


def _row_signals(row: dict[str, Any]) -> dict[str, Any] | None:
    if row.get("error"):
        return None
    attrs = row.get("attributes") or {}
    if not isinstance(attrs, dict):
        return None
    if not attrs.get("short_title"):
        return None

    severity = str(attrs.get("defect_severity") or "unknown")
    if severity not in _SEVERITY_RANK:
        severity = "unknown"
    needs_review = bool(attrs.get("needs_review", False))
    confidence = float(attrs.get("confidence") or 0.0)
    brand_tier = attrs.get("brand_tier")
    stance = row.get("suggested_stance")
    if stance not in _STANCE_RANK:
        stance = _derive_stance(
            defect_severity=severity,
            needs_review=needs_review,
            confidence=confidence,
            brand_tier=str(brand_tier) if brand_tier else None,
        )

    return {
        "defect_severity": severity,
        "defects_visible": _str_list(attrs.get("defects_visible"), limit=5),
        "talking_points": _str_list(attrs.get("talking_points"), limit=3),
        "buyer_objection_risks": _str_list(attrs.get("buyer_objection_risks"), limit=3),
        "suggested_stance": stance,
        "needs_review": needs_review,
        "confidence": confidence,
    }


def aggregate_vision_signals(listings_path: Path) -> dict[str, Any] | None:
    """Build one vision_signals dict from successful listings.json rows."""
    if not listings_path.is_file():
        return None
    try:
        payload = json.loads(listings_path.read_text())
    except json.JSONDecodeError:
        return None

    rows = payload.get("listings") or []
    if not isinstance(rows, list):
        return None

    parts = [signals for row in rows if (signals := _row_signals(row))]
    if not parts:
        return None

    defects: list[str] = []
    talking: list[str] = []
    risks: list[str] = []
    seen_d: set[str] = set()
    seen_t: set[str] = set()
    seen_r: set[str] = set()

    for part in parts:
        for text in part["defects_visible"]:
            key = text.lower()
            if key not in seen_d and len(defects) < 5:
                seen_d.add(key)
                defects.append(text)
        for text in part["talking_points"]:
            key = text.lower()
            if key not in seen_t and len(talking) < 3:
                seen_t.add(key)
                talking.append(text)
        for text in part["buyer_objection_risks"]:
            key = text.lower()
            if key not in seen_r and len(risks) < 3:
                seen_r.add(key)
                risks.append(text)

    severity = _worst_severity([str(p["defect_severity"]) for p in parts])
    stance = _worst_stance([str(p["suggested_stance"]) for p in parts])
    needs_review = any(bool(p["needs_review"]) for p in parts)

    return {
        "suggested_stance": stance,
        "defect_severity": severity,
        "defects_visible": defects,
        "talking_points": talking,
        "buyer_objection_risks": risks,
        "needs_review": needs_review,
    }
