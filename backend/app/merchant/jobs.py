"""In-memory merchant job registry with filesystem persistence."""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.merchant.paths import jobs_root
from app.merchant.schemas import (
    BundleSummary,
    GarmentAttributesRead,
    MerchantItemRead,
    MerchantJobRead,
)


@dataclass
class JobState:
    job_id: str
    root: Path
    status: str = "queued"
    message: str = "Queued"
    error: str | None = None
    items: list[MerchantItemRead] = field(default_factory=list)
    summary: BundleSummary | None = None
    published_item_ids: list[int] = field(default_factory=list)
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)

    @property
    def video_path(self) -> Path:
        return self.root / "video"

    @property
    def frames_dir(self) -> Path:
        return self.root / "frames"

    @property
    def listings_path(self) -> Path:
        return self.root / "listings.json"

    def to_read(self) -> MerchantJobRead:
        return MerchantJobRead(
            job_id=self.job_id,
            status=self.status,  # type: ignore[arg-type]
            message=self.message,
            items=list(self.items),
            summary=self.summary,
            error=self.error,
            published_item_ids=list(self.published_item_ids),
        )

    def persist_meta(self) -> None:
        payload = {
            "job_id": self.job_id,
            "status": self.status,
            "message": self.message,
            "error": self.error,
            "items": [item.model_dump() for item in self.items],
            "summary": self.summary.model_dump() if self.summary else None,
            "published_item_ids": self.published_item_ids,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "job.json").write_text(json.dumps(payload, indent=2))

    async def publish(self, event: str, data: dict[str, Any]) -> None:
        envelope = {"event": event, "data": data}
        for queue in list(self.subscribers):
            await queue.put(envelope)

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        if queue in self.subscribers:
            self.subscribers.remove(queue)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        jobs_root().mkdir(parents=True, exist_ok=True)

    def create(self) -> JobState:
        job_id = uuid.uuid4().hex
        root = jobs_root() / job_id
        root.mkdir(parents=True, exist_ok=True)
        job = JobState(job_id=job_id, root=root)
        self._jobs[job_id] = job
        job.persist_meta()
        return job

    def get(self, job_id: str) -> JobState | None:
        job = self._jobs.get(job_id)
        if job is not None:
            return job
        root = jobs_root() / job_id
        meta_path = root / "job.json"
        if not meta_path.is_file():
            return None
        payload = json.loads(meta_path.read_text())
        items = [MerchantItemRead.model_validate(row) for row in payload.get("items", [])]
        summary_raw = payload.get("summary")
        summary = BundleSummary.model_validate(summary_raw) if summary_raw else None
        if summary is None:
            summary_path = root / "summary.json"
            if summary_path.is_file():
                summary = BundleSummary.model_validate_json(summary_path.read_text())
        job = JobState(
            job_id=job_id,
            root=root,
            status=payload.get("status", "complete"),
            message=payload.get("message", ""),
            error=payload.get("error"),
            items=items,
            summary=summary,
            published_item_ids=[int(x) for x in payload.get("published_item_ids", [])],
        )
        self._jobs[job_id] = job
        return job

    def set_items_from_frames(self, job: JobState, filenames: list[str]) -> list[MerchantItemRead]:
        items = [
            MerchantItemRead(
                index=i,
                filename=name,
                image_url=f"/api/merchant/jobs/{job.job_id}/frames/{name}",
                status="pending",
            )
            for i, name in enumerate(filenames)
        ]
        job.items = items
        job.persist_meta()
        return items

    def update_item(
        self,
        job: JobState,
        *,
        index: int,
        status: str,
        attributes: GarmentAttributesRead | None = None,
        error: str | None = None,
    ) -> MerchantItemRead:
        item = job.items[index]
        updated = MerchantItemRead(
            index=item.index,
            filename=item.filename,
            image_url=item.image_url,
            status=status,  # type: ignore[arg-type]
            attributes=attributes,
            error=error,
        )
        job.items[index] = updated
        job.persist_meta()
        return updated


job_store = JobStore()
