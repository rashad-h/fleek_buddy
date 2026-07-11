"""Describe garment frames with Gemini or Qwen via LiteLLM.

Example:
  python describe_crops.py ../sam3/outputs/frames --model gemini/gemini-3.5-flash
  python describe_crops.py ../sam3/outputs/frames --model dashscope/qwen-vl-max
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from litellm import completion
from litellm.exceptions import (
    APIConnectionError,
    BadGatewayError,
    InternalServerError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)
from pydantic import ValidationError

from prompts import build_messages
from schema import CropListing, GarmentAttributes, derive_suggested_stance

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}

# LiteLLM model strings (provider/model).
DEFAULT_MODELS = {
    "gemini": "gemini/gemini-3.5-flash",
    "qwen": "dashscope/qwen-vl-max",
}

# Free-tier Gemini flash is ~5 RPM → ~12s between calls.
GEMINI_FREE_TIER_SLEEP = 13.0
DEFAULT_RETRIES = 3

RETRYABLE_EXCEPTIONS = (
    RateLimitError,
    ServiceUnavailableError,
    APIConnectionError,
    Timeout,
    InternalServerError,
    BadGatewayError,
)


def load_env() -> None:
    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env")
    load_dotenv(here.parent.parent / ".env", override=False)


def mirror_keys_to_environ() -> None:
    """LiteLLM reads provider keys from process env."""
    mapping = {
        "GEMINI_API_KEY": "GEMINI_API_KEY",
        "GOOGLE_API_KEY": "GEMINI_API_KEY",
        "DASHSCOPE_API_KEY": "DASHSCOPE_API_KEY",
        "OPENROUTER_API_KEY": "OPENROUTER_API_KEY",
        "OPENAI_API_KEY": "OPENAI_API_KEY",
    }
    for src, dest in mapping.items():
        value = (os.getenv(src) or "").strip()
        if value:
            os.environ[dest] = value


def require_provider_key(model: str) -> None:
    if model.startswith("gemini/") and not (
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    ):
        raise SystemExit(
            "Missing GEMINI_API_KEY in Vision/vlm/.env\n"
            "Get one at https://aistudio.google.com/apikey then re-run."
        )
    if model.startswith("dashscope/") and not os.getenv("DASHSCOPE_API_KEY"):
        raise SystemExit("Missing DASHSCOPE_API_KEY in Vision/vlm/.env")
    if model.startswith("openrouter/") and not os.getenv("OPENROUTER_API_KEY"):
        raise SystemExit("Missing OPENROUTER_API_KEY in Vision/vlm/.env")


def resolve_model(model: str | None) -> str:
    if model:
        return model
    alias = (os.getenv("VLM_PROVIDER") or "gemini").strip().lower()
    if alias in DEFAULT_MODELS and "/" not in alias:
        return os.getenv("VLM_MODEL") or DEFAULT_MODELS[alias]
    return os.getenv("VLM_MODEL") or DEFAULT_MODELS["gemini"]


def default_sleep_for_model(model: str) -> float:
    if model.startswith("gemini/"):
        return GEMINI_FREE_TIER_SLEEP
    return 0.0


def list_images(folder: Path) -> list[Path]:
    files = [
        p
        for p in sorted(folder.iterdir())
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    ]
    if not files:
        raise SystemExit(f"No images found in {folder}")
    return files


def category_hint_from_name(path: Path) -> str | None:
    # item_002_jacket_f007.png → jacket
    match = re.search(r"item_\d+_([a-z0-9-]+)_f\d+", path.stem, re.I)
    if match:
        return match.group(1)
    return None


def parse_attributes(raw: str) -> GarmentAttributes:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return GarmentAttributes.model_validate_json(text)


def retry_after_seconds(exc: Exception, *, attempt: int = 0) -> float:
    text = str(exc)
    match = re.search(r"[Rr]etry in ([0-9]+(?:\.[0-9]+)?)s", text)
    if match:
        return float(match.group(1)) + 1.0
    match = re.search(r'"retryDelay":\s*"([0-9]+)s"', text)
    if match:
        return float(match.group(1)) + 1.0

    name = type(exc).__name__
    if "RateLimit" in name or "429" in text or "RESOURCE_EXHAUSTED" in text:
        return 60.0
    if "ServiceUnavailable" in name or "503" in text or "UNAVAILABLE" in text:
        return 20.0 + attempt * 5.0
    if "Timeout" in name or "Connection" in name:
        return 10.0 + attempt * 5.0
    return 15.0 + attempt * 5.0


def short_error(exc: Exception) -> str:
    text = str(exc)
    if "RateLimitError" in type(exc).__name__ or "429" in text or "RESOURCE_EXHAUSTED" in text:
        return "RateLimitError: Gemini free tier quota (5 RPM). Wait and re-run with --sleep 13."
    return f"{type(exc).__name__}: {text[:240]}"


def call_completion(
    *,
    model: str,
    messages: list[dict],
    use_schema: bool,
    max_retries: int = DEFAULT_RETRIES,
):
    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": 0.1,
        "num_retries": 0,  # we handle retries ourselves
    }
    if use_schema:
        kwargs["response_format"] = GarmentAttributes

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return completion(**kwargs)
        except RETRYABLE_EXCEPTIONS as exc:
            last_exc = exc
            if attempt >= max_retries:
                raise
            wait_s = retry_after_seconds(exc, attempt=attempt)
            print(
                f"  {type(exc).__name__} — waiting {wait_s:.0f}s "
                f"then retrying ({attempt + 1}/{max_retries})...",
                flush=True,
            )
            time.sleep(wait_s)
    assert last_exc is not None
    raise last_exc


def _listing_from_attributes(
    image_path: Path,
    attributes: GarmentAttributes,
    *,
    model: str,
    error: str | None = None,
) -> CropListing:
    return CropListing(
        crop_path=str(image_path),
        attributes=attributes,
        suggested_stance=derive_suggested_stance(attributes),
        model=model,
        error=error,
    )


def _failed_listing(image_path: Path, *, model: str, error: str) -> CropListing:
    attributes = GarmentAttributes(
        category="unknown",
        color_primary="unknown",
        short_title="Needs review",
        description="Automatic extraction failed.",
        confidence=0.0,
        needs_review=True,
    )
    return _listing_from_attributes(image_path, attributes, model=model, error=error)


def describe_image(
    image_path: Path,
    *,
    model: str,
    category_hint: str | None = None,
    max_retries: int = DEFAULT_RETRIES,
) -> CropListing:
    messages = build_messages(image_path, category_hint=category_hint)
    try:
        response = call_completion(
            model=model,
            messages=messages,
            use_schema=True,
            max_retries=max_retries,
        )
        raw = response.choices[0].message.content or ""
        attributes = parse_attributes(raw)
        return _listing_from_attributes(image_path, attributes, model=model)
    except (ValidationError, json.JSONDecodeError) as exc:
        try:
            response = call_completion(
                model=model,
                messages=messages
                + [
                    {
                        "role": "user",
                        "content": "Reply with a single JSON object only. No markdown.",
                    }
                ],
                use_schema=False,
                max_retries=max_retries,
            )
            raw = response.choices[0].message.content or ""
            attributes = parse_attributes(raw)
            return _listing_from_attributes(image_path, attributes, model=model)
        except Exception as nested:
            return _failed_listing(
                image_path,
                model=model,
                error=f"{short_error(exc)} | retry: {short_error(nested)}",
            )
    except Exception as exc:
        return _failed_listing(image_path, model=model, error=short_error(exc))


def describe_image_with_retries(
    image_path: Path,
    *,
    model: str,
    category_hint: str | None = None,
    max_retries: int = DEFAULT_RETRIES,
) -> CropListing:
    """Retry the whole item if it still fails after API-level retries."""
    listing = describe_image(
        image_path,
        model=model,
        category_hint=category_hint,
        max_retries=max_retries,
    )
    for attempt in range(max_retries):
        if not listing.error:
            return listing
        wait_s = 20.0 + attempt * 5.0
        print(
            f"  item failed — waiting {wait_s:.0f}s "
            f"then retrying item ({attempt + 1}/{max_retries})...",
            flush=True,
        )
        time.sleep(wait_s)
        # One API pass per item retry; call_completion already retried above.
        listing = describe_image(
            image_path,
            model=model,
            category_hint=category_hint,
            max_retries=0,
        )
    return listing


def main() -> None:
    load_env()
    mirror_keys_to_environ()

    parser = argparse.ArgumentParser(description="VLM metadata for garment crop folders")
    parser.add_argument(
        "crops_dir",
        type=Path,
        help="Folder of crop images (png/jpg/webp)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="LiteLLM model id, e.g. gemini/gemini-3.5-flash or dashscope/qwen-vl-max",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSON path (default: <crops_dir>/../listings.json)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N images (smoke test)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=None,
        help="Seconds between calls. Default: 13 for Gemini free tier, 0 otherwise.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=DEFAULT_RETRIES,
        help=f"Retries per failed API call / item (default: {DEFAULT_RETRIES}).",
    )
    args = parser.parse_args()

    crops_dir = args.crops_dir.resolve()
    if not crops_dir.is_dir():
        raise SystemExit(f"Not a directory: {crops_dir}")

    model = resolve_model(args.model)
    require_provider_key(model)
    sleep_s = default_sleep_for_model(model) if args.sleep is None else args.sleep
    max_retries = max(0, args.retries)
    images = list_images(crops_dir)
    if args.limit is not None:
        images = images[: args.limit]

    out_path = args.out or (crops_dir.parent / "listings.json")
    out_path = out_path.resolve()

    listings: list[dict] = []
    print(f"Model: {model}")
    print(f"Images: {len(images)} from {crops_dir}")
    print(f"Retries: {max_retries} on transient failures")
    if sleep_s > 0:
        print(f"Pacing: {sleep_s:.0f}s between calls (Gemini free tier ≈ 5 RPM)")
        eta_min = (len(images) * sleep_s) / 60.0
        print(f"ETA ≈ {eta_min:.1f} min")

    for i, image_path in enumerate(images, start=1):
        hint = category_hint_from_name(image_path)
        print(f"[{i}/{len(images)}] {image_path.name} ...", flush=True)
        listing = describe_image_with_retries(
            image_path,
            model=model,
            category_hint=hint,
            max_retries=max_retries,
        )
        listings.append(listing.model_dump())
        if listing.error:
            print(f"  ERROR: {listing.error}")
        else:
            attrs = listing.attributes
            print(
                f"  {attrs.short_title} | {attrs.color_primary} | "
                f"stance={listing.suggested_stance} | "
                f"conf={attrs.confidence:.2f} review={attrs.needs_review}"
            )
        # Save progress after each image so a mid-run fail still keeps results.
        payload = {
            "model": model,
            "crops_dir": str(crops_dir),
            "count": len(listings),
            "needs_review": sum(
                1
                for row in listings
                if row["attributes"]["needs_review"] or row.get("error")
            ),
            "listings": listings,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2))

        if sleep_s > 0 and i < len(images):
            time.sleep(sleep_s)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
