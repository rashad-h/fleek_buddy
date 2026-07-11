"""Run pySceneDetect extraction and Gemini VLM describing for merchant jobs."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path

from app.merchant.env import vlm_subprocess_env
from app.merchant.jobs import JobState, job_store
from app.merchant.paths import pyscene_dir, python_for, sample_video_dir, vlm_dir
from app.merchant.schemas import GarmentAttributesRead
from app.merchant.summarize import summarize_listings

DEFAULT_EXPECTED_COUNT = 12
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def _list_frame_files(frames_dir: Path) -> list[str]:
    return sorted(
        p.name
        for p in frames_dir.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )


def _run_extract(job: JobState, *, expected_count: int) -> list[str]:
    extract_script = pyscene_dir() / "extract.py"
    if not extract_script.is_file():
        raise RuntimeError(f"Missing extractor: {extract_script}")

    python = python_for(pyscene_dir(), label="pySceneDetect")
    job.frames_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        python,
        str(extract_script),
        "--video",
        str(job.video_path),
        "--output",
        str(job.frames_dir),
        "-N",
        str(expected_count),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "extract failed").strip()
        raise RuntimeError(detail[-2000:])

    filenames = _list_frame_files(job.frames_dir)
    if not filenames:
        raise RuntimeError("Frame extraction produced no images")
    return filenames


def _attributes_from_listing(row: dict) -> GarmentAttributesRead:
    attrs = row.get("attributes") or {}
    return GarmentAttributesRead(
        category=attrs.get("category") or "unknown",
        subcategory=attrs.get("subcategory"),
        brand=attrs.get("brand"),
        color_primary=attrs.get("color_primary") or "unknown",
        material_guess=attrs.get("material_guess") or "unknown",
        condition_visible=attrs.get("condition_visible") or "unknown",
        short_title=attrs.get("short_title") or "Needs review",
        description=attrs.get("description") or "",
        confidence=float(attrs.get("confidence") or 0.0),
        needs_review=bool(attrs.get("needs_review", True)),
    )


def _listing_rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return []
    listings = payload.get("listings")
    return listings if isinstance(listings, list) else []


def _filename_for_listing(row: dict, job: JobState) -> str | None:
    crop_path = row.get("crop_path")
    if isinstance(crop_path, str) and crop_path:
        name = Path(crop_path).name
        if (job.frames_dir / name).is_file():
            return name
    return None


def _index_for_filename(job: JobState, filename: str) -> int | None:
    for item in job.items:
        if item.filename == filename:
            return item.index
    return None


async def _poll_listings_while_describing(
    job: JobState,
    process: asyncio.subprocess.Process,
) -> None:
    seen: set[str] = set()
    waiter = asyncio.create_task(process.wait())

    async def _emit_rows(rows: list[dict]) -> None:
        nonlocal seen
        for row in rows:
            filename = _filename_for_listing(row, job)
            if filename is None or filename in seen:
                continue
            index = _index_for_filename(job, filename)
            if index is None:
                continue
            seen.add(filename)
            error = row.get("error")
            if error:
                updated = job_store.update_item(
                    job,
                    index=index,
                    status="error",
                    error=str(error),
                )
            else:
                updated = job_store.update_item(
                    job,
                    index=index,
                    status="complete",
                    attributes=_attributes_from_listing(row),
                )
            await job.publish(
                "item_analyzed",
                {
                    "index": updated.index,
                    "filename": updated.filename,
                    "attributes": (
                        updated.attributes.model_dump() if updated.attributes else None
                    ),
                    "error": updated.error,
                },
            )

    while not waiter.done():
        await _emit_rows(_listing_rows(job.listings_path))
        await asyncio.sleep(0.4)

    await waiter
    await _emit_rows(_listing_rows(job.listings_path))


async def _run_describe_async(job: JobState, *, workers: int) -> None:
    describe_script = vlm_dir() / "describe_crops.py"
    python = python_for(vlm_dir(), label="vlm")
    env = vlm_subprocess_env()
    if not (env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")):
        raise RuntimeError(
            "Missing GEMINI_API_KEY. Add it to the repo root .env or Vision/vlm/.env"
        )

    log_path = job.root / "vlm.log"
    cmd = [
        python,
        "-u",
        str(describe_script),
        str(job.frames_dir),
        "--out",
        str(job.listings_path),
        "--workers",
        str(max(1, workers)),
    ]
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"$ {' '.join(cmd)}\nworkers={workers}\n\n")
        log_file.flush()
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            env=env,
        )
        await _poll_listings_while_describing(job, process)

    if process.returncode != 0:
        detail = log_path.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise RuntimeError(detail.strip() or "Gemini describe failed")


async def _set_status(job: JobState, status: str, message: str) -> None:
    job.status = status
    job.message = message
    job.persist_meta()
    await job.publish("status", {"status": status, "message": message})


async def run_job(
    job: JobState,
    *,
    expected_count: int = DEFAULT_EXPECTED_COUNT,
) -> None:
    try:
        await _set_status(job, "extracting", "Extracting garment frames from video…")
        filenames = await asyncio.to_thread(_run_extract, job, expected_count=expected_count)
        items = job_store.set_items_from_frames(job, filenames)
        await job.publish(
            "frames_ready",
            {"items": [item.model_dump() for item in items]},
        )

        # One Gemini worker per extracted frame so all images run in parallel.
        workers = max(1, len(items))
        await _set_status(
            job,
            "describing",
            f"Analyzing {len(items)} items with Gemini ({workers} workers)…",
        )
        for index in range(len(items)):
            job_store.update_item(job, index=index, status="analyzing")

        await _run_describe_async(job, workers=workers)

        for index, item in enumerate(job.items):
            if item.status == "pending" or item.status == "analyzing":
                job_store.update_item(
                    job,
                    index=index,
                    status="error",
                    error="No Gemini result returned for this frame",
                )

        await _set_status(job, "summarizing", "Building one bundle listing…")
        summary = await asyncio.to_thread(
            summarize_listings,
            job.listings_path,
            out_path=job.root / "summary.json",
        )
        job.summary = summary
        job.persist_meta()
        await job.publish("summary_ready", {"summary": summary.model_dump()})

        ok = sum(1 for item in job.items if item.status == "complete")
        await _set_status(
            job,
            "complete",
            f"Ready to publish: {summary.short_title} ({ok} garments)",
        )
        await job.publish("done", {})
    except Exception as exc:
        job.status = "error"
        job.error = str(exc)
        job.message = "Processing failed"
        job.persist_meta()
        await job.publish("error", {"detail": str(exc)})


def copy_sample_video(job: JobState, sample_name: str) -> None:
    source = sample_video_dir() / sample_name
    if not source.is_file():
        raise FileNotFoundError(f"Sample video not found: {sample_name}")
    shutil.copy2(source, job.video_path)


SAMPLE_VIDEOS = [
    "Sample-video-mp4.m4v",
    "Sample-video-4-mp4.mp4",
    "Sample-video-5-mp4.mp4",
]

DEFAULT_SAMPLE = SAMPLE_VIDEOS[0]
