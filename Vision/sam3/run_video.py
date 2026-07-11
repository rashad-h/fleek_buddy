"""Load facebook/sam3 via Hugging Face Transformers and track garments in a video.

Docs: https://huggingface.co/docs/transformers/en/model_doc/sam3_video

Note: Transformers integrates ``facebook/sam3``. The Meta ``sam3.1`` multiplex
checkpoint is a separate GitHub/HF path and is not used here.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
from accelerate import Accelerator
from huggingface_hub.errors import GatedRepoError
from transformers import Sam3VideoModel, Sam3VideoProcessor
from transformers.video_utils import load_video

from garment_track import GarmentTrack
from prompts import GARMENT_PROMPTS

MODEL_ID = "facebook/sam3"
MODEL_PAGE = "https://huggingface.co/facebook/sam3"


def gated_repo_help(exc: Exception | None = None) -> str:
    msg = str(exc).lower() if exc else ""
    if "not in the authorized list" in msg or "403" in msg:
        access_note = (
            "You are logged in, but this account has not been approved for facebook/sam3 yet.\n"
            "Open the model page, accept the license / request access, then wait for approval if needed."
        )
    else:
        access_note = (
            "Log in with: hf auth login\n"
            "Then accept the model license on the model page."
        )

    return f"""\
Cannot download facebook/sam3 (gated model).

{access_note}

  1. Open {MODEL_PAGE} while logged in as your HF user
  2. Click to agree / request access (Meta may require approval)
  3. Verify: hf auth whoami
  4. Re-run: python run_video.py data/Sample-video-mp4.m4v --max-frames 50
"""


def resolve_device() -> torch.device:
    return Accelerator().device


def load_model(model_id: str = MODEL_ID, image_size: int | None = None):
    device = resolve_device()
    dtype = torch.bfloat16 if device.type in {"cuda", "mps"} else torch.float32

    try:
        if image_size is not None:
            from transformers import Sam3VideoConfig

            config = Sam3VideoConfig.from_pretrained(model_id)
            config.image_size = image_size
            model = Sam3VideoModel.from_pretrained(model_id, config=config)
            processor = Sam3VideoProcessor.from_pretrained(
                model_id, size={"height": image_size, "width": image_size}
            )
        else:
            model = Sam3VideoModel.from_pretrained(model_id)
            processor = Sam3VideoProcessor.from_pretrained(model_id)
    except GatedRepoError as exc:
        raise SystemExit(gated_repo_help(exc)) from None
    except OSError as exc:
        if "gated repo" in str(exc).lower() or "401" in str(exc) or "403" in str(exc):
            raise SystemExit(gated_repo_help(exc)) from None
        raise

    model = model.to(device, dtype=dtype)
    model.eval()
    return model, processor, device, dtype


def prompt_category_for_object(
    object_id: int, prompt_to_obj_ids: dict[str, list[int]] | None
) -> str:
    if not prompt_to_obj_ids:
        return "garment"
    for prompt, obj_ids in prompt_to_obj_ids.items():
        if object_id in obj_ids:
            return prompt
    return "garment"


def tracks_from_frame(
    frame_index: int,
    processed_outputs: dict,
) -> list[GarmentTrack]:
    object_ids = processed_outputs["object_ids"]
    scores = processed_outputs["scores"]
    boxes = processed_outputs["boxes"]
    masks = processed_outputs.get("masks")
    prompt_to_obj_ids = processed_outputs.get("prompt_to_obj_ids")

    tracks: list[GarmentTrack] = []
    for i, object_id in enumerate(object_ids.tolist()):
        tracks.append(
            GarmentTrack(
                item_id=int(object_id),
                frame_index=frame_index,
                bounding_box=[float(x) for x in boxes[i].tolist()],
                confidence=float(scores[i].item()),
                category=prompt_category_for_object(int(object_id), prompt_to_obj_ids),
                mask=None if masks is None else masks[i],
            )
        )
    return tracks


def load_video_frames(video_path: str | Path, max_frames: int | None = None):
    """Load RGB frames; prefer OpenCV (handles .m4v on macOS better than PyAV).

    Note: OpenCV ``num_frames`` can return fewer frames than requested. Always
    use ``len(frames)`` / metadata ``frames_indices`` as the source of truth.
    """
    kwargs = {"backend": "opencv"}
    if max_frames is not None:
        kwargs["num_frames"] = max_frames
    try:
        return load_video(str(video_path), **kwargs)
    except Exception:
        kwargs["backend"] = "pyav"
        return load_video(str(video_path), **kwargs)


def run_video(
    video_path: str | Path,
    prompts: list[str],
    *,
    max_frames: int | None = None,
    image_size: int | None = None,
    model_id: str = MODEL_ID,
) -> tuple[dict[int, list[GarmentTrack]], list[int]]:
    model, processor, device, dtype = load_model(model_id=model_id, image_size=image_size)
    video_frames, metadata = load_video_frames(video_path, max_frames=max_frames)
    # Keep indices aligned with frames actually returned (OpenCV can skip undecodable ones).
    raw_indices = getattr(metadata, "frames_indices", None)
    if raw_indices is not None and len(raw_indices) == len(video_frames):
        source_indices = [int(i) for i in raw_indices]
    else:
        source_indices = list(range(len(video_frames)))
        if raw_indices is not None:
            print(
                f"Warning: metadata had {len(raw_indices)} indices but "
                f"{len(video_frames)} frames loaded; using 0..{len(video_frames)-1}"
            )

    inference_session = processor.init_video_session(
        video=video_frames,
        inference_device=device,
        processing_device="cpu",
        video_storage_device="cpu",
        dtype=dtype,
    )
    processor.add_text_prompt(inference_session, prompts)

    tracks_by_frame: dict[int, list[GarmentTrack]] = {}
    # Track all loaded frames, not the requested max_frames count.
    for model_outputs in model.propagate_in_video_iterator(
        inference_session=inference_session,
        max_frame_num_to_track=len(video_frames),
        show_progress_bar=True,
    ):
        processed = processor.postprocess_outputs(inference_session, model_outputs)
        frame_idx = int(model_outputs.frame_idx)
        tracks_by_frame[frame_idx] = tracks_from_frame(frame_idx, processed)

    return tracks_by_frame, source_indices


def summarize(tracks_by_frame: dict[int, list[GarmentTrack]]) -> dict:
    item_ids: set[int] = set()
    categories: dict[str, set[int]] = {}
    for tracks in tracks_by_frame.values():
        for track in tracks:
            item_ids.add(track.item_id)
            categories.setdefault(track.category, set()).add(track.item_id)

    return {
        "frames": len(tracks_by_frame),
        "unique_items": len(item_ids),
        "item_ids": sorted(item_ids),
        "per_prompt": {k: sorted(v) for k, v in sorted(categories.items())},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="SAM 3 video garment tracking (HF Transformers)")
    parser.add_argument("video", type=Path, help="Path to a local video file")
    parser.add_argument(
        "--prompts",
        nargs="+",
        default=GARMENT_PROMPTS,
        help="Short noun prompts (default: garment categories)",
    )
    parser.add_argument("--max-frames", type=int, default=None, help="Limit frames tracked")
    parser.add_argument(
        "--image-size",
        type=int,
        default=None,
        help="Optional lower resolution (e.g. 560). Default model size is 1008.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/tracks.json"),
        help="JSON summary path (masks omitted)",
    )
    args = parser.parse_args()

    if not args.video.exists():
        raise SystemExit(f"Video not found: {args.video}")

    tracks_by_frame, source_indices = run_video(
        args.video,
        args.prompts,
        max_frames=args.max_frames,
        image_size=args.image_size,
    )
    summary = summarize(tracks_by_frame)
    payload = {
        "video": str(args.video),
        "prompts": args.prompts,
        "max_frames_requested": args.max_frames,
        "source_frame_indices": source_indices,
        "summary": summary,
        "frames": {
            str(frame_idx): [t.to_public_dict() for t in tracks]
            for frame_idx, tracks in sorted(tracks_by_frame.items())
        },
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
