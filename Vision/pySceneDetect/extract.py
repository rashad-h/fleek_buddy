#!/usr/bin/env python3
"""Extract one sharp frame per clothing item from a flip-through haul video.

Overfit to Vision/sample_video/Sample-video-mp4.m4v (~15 distinct garments):
flip peaks (motion spikes) mark transitions; we pick a settled sharp frame after
each flip, then globally dedupe near-identical holds.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Extract one sharp JPEG per garment from a clothing haul video.",
    )
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument(
        "--min-sharpness",
        type=float,
        default=28.0,
        help="Skip frames below this center-crop Laplacian variance (default: 28)",
    )
    p.add_argument(
        "--peak-percentile",
        type=float,
        default=70.0,
        help="Motion peaks above this percentile count as flips (default: 70)",
    )
    p.add_argument(
        "--min-peak-sep",
        type=float,
        default=0.42,
        help="Minimum seconds between flip peaks (default: 0.42)",
    )
    p.add_argument(
        "--hold-percentile",
        type=float,
        default=40.0,
        help="Post-flip settle when motion drops below this percentile (default: 40)",
    )
    p.add_argument(
        "--search-window",
        type=float,
        default=0.55,
        help="Seconds after settle to search for sharpest frame (default: 0.55)",
    )
    p.add_argument(
        "--dedupe-corr",
        type=float,
        default=0.97,
        help="Merge holds with HSV hist correlation above this (default: 0.97)",
    )
    p.add_argument(
        "--dedupe-lab",
        type=float,
        default=5.0,
        help="Also require mean LAB distance below this to merge (default: 5)",
    )
    return p.parse_args()


def garment_roi(h: int, w: int) -> tuple[int, int, int, int]:
    """Focus on garment body; ignore bottom overlay and side hand entry."""
    return int(h * 0.10), int(h * 0.70), int(w * 0.18), int(w * 0.82)


def crop(frame, roi: tuple[int, int, int, int]):
    y0, y1, x0, x1 = roi
    return frame[y0:y1, x0:x1]


def sharpness(frame, roi: tuple[int, int, int, int]) -> float:
    gray = cv2.cvtColor(crop(frame, roi), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def hsv_hist(frame, roi: tuple[int, int, int, int]):
    hsv = cv2.cvtColor(crop(frame, roi), cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [30, 40], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def mean_lab(frame, roi: tuple[int, int, int, int]) -> np.ndarray:
    lab = cv2.cvtColor(crop(frame, roi), cv2.COLOR_BGR2LAB)
    return lab.reshape(-1, 3).mean(axis=0)


def falling_penalty(frame, h: int, w: int) -> float:
    """High score = previous garment still blurred at bottom of frame."""
    y0, y1 = int(h * 0.58), int(h * 0.88)
    x0, x1 = int(w * 0.20), int(w * 0.80)
    region = frame[y0:y1, x0:x1]
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    # Motion blur → low Laplacian; reward frames where bottom is also reasonably sharp
    # (no flying previous item). Return inverse as penalty.
    var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    return max(0.0, 25.0 - var)


def load_video(path: Path) -> tuple[list, float]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"could not open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frames: list = []
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            break
        frames.append(frame)
    cap.release()
    if not frames:
        raise RuntimeError(f"no frames read from: {path}")
    return frames, fps


def motion_curve(frames: list, roi: tuple[int, int, int, int], fps: float) -> np.ndarray:
    n = len(frames)
    motion = np.zeros(n, dtype=np.float64)
    prev = cv2.cvtColor(crop(frames[0], roi), cv2.COLOR_BGR2GRAY)
    for i in range(1, n):
        gray = cv2.cvtColor(crop(frames[i], roi), cv2.COLOR_BGR2GRAY)
        motion[i] = float(np.mean(cv2.absdiff(prev, gray)))
        prev = gray
    k = max(3, int(round(fps * 0.08)) | 1)
    return np.convolve(motion, np.ones(k) / k, mode="same")


def find_flip_peaks(
    smooth: np.ndarray, fps: float, peak_pct: float, min_sep: float
) -> list[int]:
    thr = float(np.percentile(smooth, peak_pct))
    min_sep_f = max(1, int(fps * min_sep))
    peaks: list[int] = []
    n = len(smooth)
    for i in range(2, n - 2):
        if not (smooth[i] >= smooth[i - 1] and smooth[i] >= smooth[i + 1]):
            continue
        if smooth[i] < thr:
            continue
        if not peaks or i - peaks[-1] >= min_sep_f:
            peaks.append(i)
        elif smooth[i] > smooth[peaks[-1]]:
            peaks[-1] = i
    return peaks


def pick_in_range(
    frames: list,
    smooth: np.ndarray,
    roi: tuple[int, int, int, int],
    lo: int,
    hi: int,
) -> int | None:
    if hi <= lo:
        return None
    h, w = frames[0].shape[:2]
    best_i, best = None, -1e18
    for i in range(lo, hi):
        score = (
            sharpness(frames[i], roi)
            - float(smooth[i]) * 1.5
            - falling_penalty(frames[i], h, w) * 0.6
        )
        if score > best:
            best, best_i = score, i
    return best_i


def pick_after_flip(
    frames: list,
    smooth: np.ndarray,
    roi: tuple[int, int, int, int],
    fps: float,
    peak: int,
    next_peak: int | None,
    hold_pct: float,
    search_window: float,
) -> int | None:
    hold_thr = float(np.percentile(smooth, hold_pct))
    end = next_peak if next_peak is not None else len(frames) - 1
    start = min(end - 1, peak + max(1, int(fps * 0.08)))
    if start >= end:
        return None

    settled = None
    for i in range(start, end):
        if smooth[i] <= hold_thr:
            settled = i
            break
    if settled is None:
        # lowest-motion frame in segment interior
        span = end - start
        lo = start + int(span * 0.2)
        hi = end - int(span * 0.1)
        if hi <= lo:
            lo, hi = start, end
        return int(lo + np.argmin(smooth[lo:hi]))

    win_end = min(end, settled + max(2, int(fps * search_window)))
    return pick_in_range(frames, smooth, roi, settled, win_end)


def pick_initial(
    frames: list,
    smooth: np.ndarray,
    roi: tuple[int, int, int, int],
    fps: float,
    first_peak: int,
) -> int | None:
    hi = max(1, first_peak - int(fps * 0.05))
    return pick_in_range(frames, smooth, roi, 0, hi)


def similar(
    frames: list,
    a: int,
    b: int,
    roi: tuple[int, int, int, int],
    corr_thr: float,
    lab_thr: float,
) -> bool:
    corr = cv2.compareHist(
        hsv_hist(frames[a], roi),
        hsv_hist(frames[b], roi),
        cv2.HISTCMP_CORREL,
    )
    dlab = float(np.linalg.norm(mean_lab(frames[a], roi) - mean_lab(frames[b], roi)))
    return corr >= corr_thr and dlab <= lab_thr


def global_dedupe(
    frames: list,
    picks: list[int],
    roi: tuple[int, int, int, int],
    corr_thr: float,
    lab_thr: float,
) -> list[int]:
    """Keep sharpest frame per visual cluster (order-preserving)."""
    if not picks:
        return []

    scores = [sharpness(frames[i], roi) for i in picks]
    kept: list[int] = []
    kept_scores: list[float] = []

    for idx, frame_i in enumerate(picks):
        merged = False
        for k, kept_i in enumerate(kept):
            if similar(frames, frame_i, kept_i, roi, corr_thr, lab_thr):
                if scores[idx] > kept_scores[k]:
                    kept[k] = frame_i
                    kept_scores[k] = scores[idx]
                merged = True
                break
        if not merged:
            kept.append(frame_i)
            kept_scores.append(scores[idx])

    # Restore chronological order
    return sorted(kept)


def main() -> int:
    args = parse_args()

    if not args.video.is_file():
        print(f"Error: video not found: {args.video}", file=sys.stderr)
        return 1

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Loading {args.video} …")
    try:
        frames, fps = load_video(args.video)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    h, w = frames[0].shape[:2]
    roi = garment_roi(h, w)
    print(f"{len(frames)} frames @ {fps:.2f} fps ({len(frames) / fps:.1f}s)")

    print("Detecting flips (motion peaks) …")
    smooth = motion_curve(frames, roi, fps)
    peaks = find_flip_peaks(
        smooth, fps, peak_pct=args.peak_percentile, min_sep=args.min_peak_sep
    )
    print(f"Found {len(peaks)} flip peak(s).")

    candidates: list[int] = []
    if peaks:
        initial = pick_initial(frames, smooth, roi, fps, peaks[0])
        if initial is not None:
            candidates.append(initial)
        for i, peak in enumerate(peaks):
            nxt = peaks[i + 1] if i + 1 < len(peaks) else None
            pick = pick_after_flip(
                frames,
                smooth,
                roi,
                fps,
                peak,
                nxt,
                hold_pct=args.hold_percentile,
                search_window=args.search_window,
            )
            if pick is not None:
                candidates.append(pick)
    else:
        # No flips — single best frame
        pick = pick_in_range(frames, smooth, roi, 0, len(frames))
        if pick is not None:
            candidates.append(pick)

    # Drop near-duplicate consecutive candidates first, then global cluster
    consecutive: list[int] = []
    for c in candidates:
        if consecutive and similar(
            frames, c, consecutive[-1], roi, args.dedupe_corr, args.dedupe_lab
        ):
            if sharpness(frames[c], roi) > sharpness(frames[consecutive[-1]], roi):
                consecutive[-1] = c
            continue
        consecutive.append(c)

    picks = global_dedupe(
        frames, consecutive, roi, corr_thr=args.dedupe_corr, lab_thr=args.dedupe_lab
    )
    print(
        f"Candidates {len(candidates)} → {len(consecutive)} after consecutive "
        f"dedupe → {len(picks)} unique.\n"
    )

    saved = 0
    skipped = 0
    item_num = 0

    for i, frame_idx in enumerate(picks, start=1):
        frame = frames[frame_idx]
        score = sharpness(frame, roi)
        if score < args.min_sharpness:
            skipped += 1
            print(
                f"Item candidate {i} @ {frame_idx / fps:.2f}s → skipped "
                f"(sharpness: {score:.1f} < {args.min_sharpness})"
            )
            continue

        item_num += 1
        filename = f"item_{item_num:03d}.jpg"
        ok = cv2.imwrite(
            str(args.output / filename), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 95]
        )
        if not ok:
            skipped += 1
            print(f"Item candidate {i} → failed to write {filename}")
            continue

        (args.output / f"item_{item_num:03d}.sharpness.txt").write_text(
            f"{score:.1f}\n", encoding="utf-8"
        )
        saved += 1
        print(
            f"Flip→hold @ {frame_idx / fps:.2f}s → saved {filename} "
            f"(sharpness: {score:.1f})"
        )

    print("\n── Summary ──")
    print(f"Flip peaks detected:   {len(peaks)}")
    print(f"Unique items kept:     {len(picks)}")
    print(f"Total saved:           {saved}")
    print(f"Total skipped:         {skipped}")
    print(f"Output folder:         {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
