"""Merchant video upload and cataloging endpoints."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.merchant.jobs import JobState, job_store
from app.merchant.pipeline import (
    DEFAULT_EXPECTED_COUNT,
    DEFAULT_SAMPLE,
    SAMPLE_VIDEOS,
    copy_sample_video,
    run_job,
)
from app.merchant.publish import publish_job_to_catalogue
from app.merchant.schemas import (
    MerchantJobCreateResponse,
    MerchantJobRead,
    MerchantPublishResponse,
)
from app.models import Item

router = APIRouter(prefix="/merchant", tags=["merchant"])

SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".m4v", ".mov", ".webm", ".mkv"}


def _clamp_expected_count(raw: int | None) -> int:
    if raw is None:
        return DEFAULT_EXPECTED_COUNT
    return max(1, min(int(raw), 40))


async def _save_upload(job: JobState, upload: UploadFile) -> None:
    suffix = Path(upload.filename or "upload.mp4").suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video type. Allowed: {', '.join(sorted(ALLOWED_VIDEO_SUFFIXES))}",
        )
    destination = job.video_path.with_suffix(suffix)
    job.root.mkdir(parents=True, exist_ok=True)
    content = await upload.read()
    destination.write_bytes(content)
    if destination != job.video_path:
        if job.video_path.exists():
            job.video_path.unlink()
        destination.rename(job.video_path)


def _start_pipeline(
    job: JobState,
    background: BackgroundTasks,
    *,
    expected_count: int,
) -> MerchantJobCreateResponse:
    background.add_task(run_job, job, expected_count=expected_count)
    return MerchantJobCreateResponse(job_id=job.job_id)


@router.post("/jobs", response_model=MerchantJobCreateResponse, status_code=201)
async def create_job(
    background: BackgroundTasks,
    video: UploadFile = File(...),
    expected_count: int = Form(DEFAULT_EXPECTED_COUNT),
) -> MerchantJobCreateResponse:
    """Upload a supplier video and start live frame extraction + Gemini analysis."""
    job = job_store.create()
    await _save_upload(job, video)
    return _start_pipeline(
        job,
        background,
        expected_count=_clamp_expected_count(expected_count),
    )


@router.post("/jobs/sample", response_model=MerchantJobCreateResponse, status_code=201)
async def create_sample_job(
    background: BackgroundTasks,
    expected_count: int = Form(DEFAULT_EXPECTED_COUNT),
) -> MerchantJobCreateResponse:
    """Start processing with a bundled demo video (no upload required)."""
    job = job_store.create()
    try:
        copy_sample_video(job, DEFAULT_SAMPLE)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _start_pipeline(
        job,
        background,
        expected_count=_clamp_expected_count(expected_count),
    )


@router.get("/samples")
async def list_samples() -> dict[str, list[str]]:
    return {"samples": SAMPLE_VIDEOS, "default": DEFAULT_SAMPLE}


@router.get("/jobs/{job_id}", response_model=MerchantJobRead)
async def get_job(job_id: str) -> MerchantJobRead:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_read()


@router.post("/jobs/{job_id}/publish", response_model=MerchantPublishResponse)
async def publish_job(
    job_id: str,
    session: AsyncSession = Depends(get_session),
) -> MerchantPublishResponse:
    """Create one buyer marketplace listing for the whole video haul."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "complete":
        raise HTTPException(status_code=409, detail="Job is not complete yet")
    if job.published_item_ids:
        # Allow re-publish if the catalogue rows were deleted (e.g. demo reset).
        existing = await session.get(Item, job.published_item_ids[0])
        if existing is not None:
            return MerchantPublishResponse(
                job_id=job.job_id,
                item_ids=job.published_item_ids,
                count=len(job.published_item_ids),
            )
        job.published_item_ids = []
        job.persist_meta()
    if not (job.root / "summary.json").is_file():
        raise HTTPException(status_code=400, detail="No bundle summary for this job")

    try:
        item_ids = await publish_job_to_catalogue(session, job)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not item_ids:
        raise HTTPException(status_code=400, detail="Nothing to publish")
    job.published_item_ids = item_ids
    job.persist_meta()
    return MerchantPublishResponse(job_id=job.job_id, item_ids=item_ids, count=len(item_ids))


@router.get("/jobs/{job_id}/frames/{filename}")
async def get_frame(job_id: str, filename: str) -> FileResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    safe_name = Path(filename).name
    frame_path = job.frames_dir / safe_name
    if not frame_path.is_file():
        raise HTTPException(status_code=404, detail="Frame not found")
    return FileResponse(frame_path)


async def _sse_stream(job: JobState) -> asyncio.AsyncIterator[str]:
    queue = job.subscribe()
    try:
        snapshot = job.to_read()
        yield f"event: status\ndata: {json.dumps({'status': snapshot.status, 'message': snapshot.message})}\n\n"
        if snapshot.items:
            yield (
                f"event: frames_ready\ndata: "
                f"{json.dumps({'items': [item.model_dump() for item in snapshot.items]})}\n\n"
            )
        for item in snapshot.items:
            if item.status in {"complete", "error"}:
                yield (
                    f"event: item_analyzed\ndata: "
                    f"{json.dumps({'index': item.index, 'filename': item.filename, 'attributes': item.attributes.model_dump() if item.attributes else None, 'error': item.error})}\n\n"
                )
        if snapshot.summary is not None:
            yield (
                f"event: summary_ready\ndata: "
                f"{json.dumps({'summary': snapshot.summary.model_dump()})}\n\n"
            )
        if snapshot.status == "complete":
            yield "event: done\ndata: {}\n\n"
            return
        if snapshot.status == "error":
            yield f"event: error\ndata: {json.dumps({'detail': snapshot.error or 'Processing failed'})}\n\n"
            return

        while True:
            try:
                envelope = await asyncio.wait_for(queue.get(), timeout=30.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            event = envelope["event"]
            data = json.dumps(envelope["data"])
            yield f"event: {event}\ndata: {data}\n\n"
            if event in {"done", "error"}:
                break
    finally:
        job.unsubscribe(queue)


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return StreamingResponse(
        _sse_stream(job),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
