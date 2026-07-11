"""Regression checks for vision-signals wiring (no DB required)."""

from __future__ import annotations

import json
import tempfile
from decimal import Decimal
from pathlib import Path

from app.agent.context import (
    CONTEXT_PROVIDERS,
    NegotiationContext,
    build_system_prompt,
    item_listing_block,
    vision_signals_block,
)
from app.merchant.jobs import JobState, JobStore
from app.merchant.pipeline import _attributes_from_listing, _stance_from_listing
from app.merchant.schemas import GarmentAttributesRead, MerchantItemRead, MerchantJobRead
from app.merchant.vision_signals import aggregate_vision_signals
from app.models import Item, Negotiation
from app.schemas import ItemRead


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def test_old_attributes_still_parse() -> None:
    """Pre-change Gemini payloads without lean fields must still validate."""
    attrs = GarmentAttributesRead(
        category="jacket",
        subcategory=None,
        brand="Nike",
        color_primary="black",
        material_guess="unknown",
        condition_visible="used_good",
        short_title="Black Nike jacket",
        description="A jacket.",
        confidence=0.8,
        needs_review=False,
    )
    _assert(attrs.defects_visible == [], "defaults defects_visible")
    _assert(attrs.defect_severity == "unknown", "defaults defect_severity")
    _assert(attrs.talking_points == [], "defaults talking_points")
    _assert(attrs.buyer_objection_risks == [], "defaults risks")


def test_old_job_json_items_still_parse() -> None:
    """job.json written before suggested_stance must still load."""
    raw = {
        "index": 0,
        "filename": "item_000.jpg",
        "image_url": "/api/merchant/jobs/x/frames/item_000.jpg",
        "status": "complete",
        "attributes": {
            "category": "vest",
            "subcategory": "puffer",
            "brand": None,
            "color_primary": "black",
            "material_guess": "synthetic",
            "condition_visible": "used_good",
            "short_title": "Black vest",
            "description": "A vest.",
            "confidence": 0.9,
            "needs_review": False,
        },
        "error": None,
    }
    item = MerchantItemRead.model_validate(raw)
    _assert(item.suggested_stance is None, "old items have no stance")
    _assert(item.attributes is not None, "attrs present")
    _assert(item.attributes.defects_visible == [], "attrs defaults")


def test_attributes_from_listing_legacy_and_new() -> None:
    legacy = {
        "crop_path": "a.jpg",
        "attributes": {
            "category": "jacket",
            "color_primary": "red",
            "condition_visible": "used_good",
            "short_title": "Red jacket",
            "description": "desc",
            "confidence": 0.7,
            "needs_review": False,
        },
        "error": None,
    }
    attrs = _attributes_from_listing(legacy)
    _assert(attrs.short_title == "Red jacket", "legacy title")
    _assert(_stance_from_listing(legacy) is None, "no stance on legacy")

    modern = {
        "crop_path": "b.jpg",
        "attributes": {
            "category": "jacket",
            "color_primary": "blue",
            "condition_visible": "used_fair",
            "short_title": "Blue jacket",
            "description": "desc",
            "confidence": 0.6,
            "needs_review": True,
            "defects_visible": ["stain"],
            "defect_severity": "minor",
            "talking_points": ["logo clear", "extra1", "extra2", "extra3"],
            "buyer_objection_risks": ["stain"],
        },
        "suggested_stance": "flexible",
        "error": None,
    }
    attrs2 = _attributes_from_listing(modern)
    _assert(attrs2.defects_visible == ["stain"], "defects mapped")
    _assert(attrs2.defect_severity == "minor", "severity mapped")
    _assert(len(attrs2.talking_points) == 3, "talking points capped at 3")
    _assert(_stance_from_listing(modern) == "flexible", "stance mapped")


def test_aggregate_empty_and_errors() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "listings.json"
        _assert(aggregate_vision_signals(path) is None, "missing file")

        path.write_text("{not json")
        _assert(aggregate_vision_signals(path) is None, "bad json")

        path.write_text(json.dumps({"listings": []}))
        _assert(aggregate_vision_signals(path) is None, "empty listings")

        path.write_text(
            json.dumps(
                {
                    "listings": [
                        {"error": "boom", "attributes": {"short_title": "x"}},
                        {
                            "error": None,
                            "attributes": {"short_title": "", "defect_severity": "major"},
                        },
                    ]
                }
            )
        )
        _assert(aggregate_vision_signals(path) is None, "no successful rows")


def test_aggregate_worst_case_merge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "listings.json"
        path.write_text(
            json.dumps(
                {
                    "listings": [
                        {
                            "error": None,
                            "suggested_stance": "firm",
                            "attributes": {
                                "short_title": "A",
                                "defect_severity": "none",
                                "defects_visible": [],
                                "talking_points": ["logo clear"],
                                "buyer_objection_risks": ["size missing"],
                                "needs_review": False,
                                "confidence": 0.9,
                                "brand_tier": "premium",
                            },
                        },
                        {
                            "error": None,
                            "suggested_stance": "flexible",
                            "attributes": {
                                "short_title": "B",
                                "defect_severity": "minor",
                                "defects_visible": ["stain on front"],
                                "talking_points": ["zipper intact"],
                                "buyer_objection_risks": ["visible stain"],
                                "needs_review": True,
                                "confidence": 0.7,
                            },
                        },
                    ]
                }
            )
        )
        sig = aggregate_vision_signals(path)
        _assert(sig is not None, "got signals")
        assert sig is not None
        _assert(sig["suggested_stance"] == "flexible", "worst stance")
        _assert(sig["defect_severity"] == "minor", "worst severity")
        _assert(sig["needs_review"] is True, "any needs_review")
        _assert("stain on front" in sig["defects_visible"], "defects merged")
        _assert(len(sig["talking_points"]) <= 3, "cap talking")
        _assert(len(sig["buyer_objection_risks"]) <= 3, "cap risks")


def test_job_store_update_preserves_flow() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "job"
        root.mkdir()
        store = JobStore()
        # Bypass create() uuid path: build JobState directly
        job = JobState(job_id="testjob", root=root)
        store._jobs[job.job_id] = job  # noqa: SLF001
        store.set_items_from_frames(job, ["item_000.jpg"])
        attrs = GarmentAttributesRead(
            category="jacket",
            color_primary="black",
            condition_visible="used_good",
            short_title="Black jacket",
            description="desc",
            confidence=0.8,
            needs_review=False,
            defects_visible=["hole"],
            defect_severity="major",
            talking_points=["brand clear"],
            buyer_objection_risks=["hole"],
        )
        updated = store.update_item(
            job,
            index=0,
            status="complete",
            attributes=attrs,
            suggested_stance="flexible",
        )
        _assert(updated.suggested_stance == "flexible", "stance saved")
        reloaded = MerchantJobRead.model_validate(
            json.loads((root / "job.json").read_text())
            | {
                "job_id": "testjob",
                "status": "complete",
                "message": "ok",
                "error": None,
                "summary": None,
                "published_item_ids": [],
            }
        )
        # Persist shape is items-only inside job.json; validate item roundtrip
        raw = json.loads((root / "job.json").read_text())
        item = MerchantItemRead.model_validate(raw["items"][0])
        _assert(item.attributes is not None, "attrs persisted")
        _assert(item.attributes.defects_visible == ["hole"], "defects persisted")
        _assert(item.suggested_stance == "flexible", "stance persisted")
        _assert(reloaded is not None, "job schema ok")


def test_agent_context_optional_and_present() -> None:
    item = Item(
        id=1,
        title="Haul",
        brand="Mixed",
        vendor_name="Video Catalog",
        description="Bundle",
        category="Mixed",
        condition="AB Grade Vintage",
        sizes="Mixed",
        piece_count=2,
        price_per_piece=Decimal("8.50"),
        bundle_price=Decimal("17.00"),
        shipping_days_min=7,
        shipping_days_max=14,
        image_url="/x.jpg",
        buying_price=Decimal("7.00"),
        lowest_bundle_price=Decimal("10.00"),
        lowest_price_per_piece=Decimal("5.00"),
        vision_signals=None,
    )
    neg = Negotiation(id=1, item_id=1, buyer_id="b1", status="open")
    ctx = NegotiationContext(item=item, negotiation=neg, messages=[])
    _assert(vision_signals_block(ctx) is None, "no block without signals")
    prompt = build_system_prompt(ctx)
    _assert("## The listing" in prompt, "listing still present")
    _assert("## Vision signals" not in prompt, "vision omitted when null")
    _assert(CONTEXT_PROVIDERS[0] is item_listing_block, "listing first")
    _assert(CONTEXT_PROVIDERS[1] is vision_signals_block, "vision second")

    item.vision_signals = {
        "suggested_stance": "flexible",
        "defect_severity": "minor",
        "defects_visible": ["stain on front"],
        "talking_points": ["logo clear"],
        "buyer_objection_risks": ["visible stain"],
        "needs_review": True,
    }
    block = vision_signals_block(ctx)
    _assert(block is not None and "stance: flexible" in block, "block rendered")
    prompt2 = build_system_prompt(ctx)
    _assert("## Vision signals" in prompt2, "vision in system prompt")
    _assert("stain on front" in prompt2, "defect text in prompt")


def test_public_item_read_excludes_vision() -> None:
    fields = set(ItemRead.model_fields)
    _assert("vision_signals" not in fields, "vision not public")
    _assert("buying_price" not in fields, "floors still private")
    _assert("grades" not in fields, "grades still private")


def main() -> None:
    tests = [
        test_old_attributes_still_parse,
        test_old_job_json_items_still_parse,
        test_attributes_from_listing_legacy_and_new,
        test_aggregate_empty_and_errors,
        test_aggregate_worst_case_merge,
        test_job_store_update_preserves_flow,
        test_agent_context_optional_and_present,
        test_public_item_read_excludes_vision,
    ]
    for test in tests:
        test()
        print(f"OK  {test.__name__}")
    print(f"\nAll {len(tests)} checks passed.")


if __name__ == "__main__":
    main()
