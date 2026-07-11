#!/usr/bin/env python3
"""Extract one sharp frame per clothing item from a flip-through haul video.

Flip peaks (motion spikes) mark transitions; we pick a settled sharp frame after
each flip, then dedupe near-identical holds.

Sharpness is scored on a resolution-normalized copy (default short-side 720) and
gated relative to that video's candidate median, so one threshold works across
clips with different resolutions/compression.

Optional --expected-count N: after sharpness gating, if we still have more than N
holds, drop low change_score / near-duplicate pairs first.

Consecutive holds are merged when change_score = motion × appearance_delta is
low (same garment re-hold), not only when hist corr is high.
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
        "-N",
        "--expected-count",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Expected number of garments. When set, keep all detected flips, then "
            "after sharpness gating trim extras by near-duplicate similarity "
            "(fallback: lowest sharpness). Omit for unconstrained detection."
        ),
    )
    p.add_argument(
        "--score-size",
        type=int,
        default=720,
        help="Resize short side to this many px before sharpness scoring (default: 720)",
    )
    p.add_argument(
        "--sharpness-median-ratio",
        type=float,
        default=0.4,
        help=(
            "Keep holds with normalized sharpness >= median(candidates) * ratio "
            "(default: 0.4)"
        ),
    )
    p.add_argument(
        "--min-sharpness",
        type=float,
        default=5.0,
        help=(
            "Absolute floor on normalized (@score-size) Laplacian variance; "
            "kills empty/black frames (default: 5.0)"
        ),
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
    p.add_argument(
        "--change-median-ratio",
        type=float,
        default=0.45,
        help=(
            "Merge consecutive holds if change_score < median(pair scores)×ratio "
            "(default: 0.45). change_score = normalized_motion × appearance_delta."
        ),
    )
    p.add_argument(
        "--min-change-score",
        type=float,
        default=0.25,
        help="Absolute floor for change_score merge gate (default: 0.25)",
    )
    p.add_argument(
        "--max-change-motion",
        type=float,
        default=0.70,
        help=(
            "Only apply change_score merges when intervening motion is below this "
            "fraction of median peak (default: 0.70). Protects strong flips between "
            "similar-looking garments."
        ),
    )
    return p.parse_args()


def garment_roi(h: int, w: int) -> tuple[int, int, int, int]:
    """Focus on garment body; ignore bottom overlay and side hand entry."""
    return int(h * 0.10), int(h * 0.70), int(w * 0.18), int(w * 0.82)


def crop(frame, roi: tuple[int, int, int, int]):
    y0, y1, x0, x1 = roi
    return frame[y0:y1, x0:x1]


def resize_for_score(frame, short_side: int):
    """Return a copy with min(h, w) == short_side (no-op if already smaller)."""
    h, w = frame.shape[:2]
    current = min(h, w)
    if current <= 0 or current == short_side:
        return frame
    scale = short_side / current
    return cv2.resize(
        frame,
        (max(1, int(round(w * scale))), max(1, int(round(h * scale)))),
        interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR,
    )


def sharpness_normalized(frame, short_side: int) -> float:
    """Laplacian variance on garment ROI after resolution standardization."""
    scored = resize_for_score(frame, short_side)
    roi = garment_roi(*scored.shape[:2])
    gray = cv2.cvtColor(crop(scored, roi), cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def hsv_hist(frame, roi: tuple[int, int, int, int]):
    hsv = cv2.cvtColor(crop(frame, roi), cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [30, 40], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist


def mean_lab(frame, roi: tuple[int, int, int, int]) -> np.ndarray:
    lab = cv2.cvtColor(crop(frame, roi), cv2.COLOR_BGR2LAB)
    return lab.reshape(-1, 3).mean(axis=0)


def falling_penalty(frame, short_side: int) -> float:
    """High score = previous garment still blurred at bottom of frame."""
    scored = resize_for_score(frame, short_side)
    h, w = scored.shape[:2]
    y0, y1 = int(h * 0.58), int(h * 0.88)
    x0, x1 = int(w * 0.20), int(w * 0.80)
    gray = cv2.cvtColor(scored[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
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


def pair_similarity(
    frames: list,
    a: int,
    b: int,
    roi: tuple[int, int, int, int],
) -> tuple[float, float]:
    corr = cv2.compareHist(
        hsv_hist(frames[a], roi),
        hsv_hist(frames[b], roi),
        cv2.HISTCMP_CORREL,
    )
    dlab = float(np.linalg.norm(mean_lab(frames[a], roi) - mean_lab(frames[b], roi)))
    return float(corr), dlab


def trim_to_expected_count(
    frames: list,
    picks: list[int],
    scores: list[float],
    roi: tuple[int, int, int, int],
    expected_count: int,
    fps: float,
    smooth: np.ndarray | None = None,
    peak_ref: float = 1.0,
    change_gate: float = 0.35,
    dup_corr: float = 0.90,
    dup_lab: float = 8.0,
) -> tuple[list[int], list[float], int]:
    """Trim to N by dropping low change_score pairs first, else lowest sharpness."""
    if expected_count < 1 or len(picks) <= expected_count:
        return picks, scores, 0

    picks = list(picks)
    scores = list(scores)
    trimmed = 0
    if smooth is None:
        smooth = np.ones(max(picks) + 1 if picks else 1, dtype=np.float64)

    while len(picks) > expected_count:
        drop: int | None = None
        best_key: tuple | None = None
        best_cs = 0.0
        best_corr = -1.0

        for i in range(len(picks) - 1):
            cs, _m, _a, corr = change_score(
                frames, picks[i], picks[i + 1], roi, smooth, peak_ref
            )
            dlab = pair_similarity(frames, picks[i], picks[i + 1], roi)[1]
            is_low_change = cs < change_gate
            is_hist_dup = corr >= dup_corr and dlab <= dup_lab
            if not (is_low_change or is_hist_dup):
                continue
            # Prefer lowest change_score (most likely same garment)
            key = (-cs, corr)
            if best_key is None or key > best_key:
                best_key = key
                best_cs = cs
                best_corr = corr
                drop = i if scores[i] <= scores[i + 1] else i + 1

        if drop is None:
            for i in range(len(picks)):
                for j in range(i + 1, len(picks)):
                    corr, dlab = pair_similarity(frames, picks[i], picks[j], roi)
                    if corr < dup_corr or dlab > dup_lab:
                        continue
                    key = (0.0, corr)
                    if best_key is None or key > best_key:
                        best_key = key
                        best_cs = -1.0
                        best_corr = corr
                        drop = i if scores[i] <= scores[j] else j

        if drop is None:
            drop = min(range(len(picks)), key=lambda k: scores[k])
            reason = "lowest sharpness"
        elif best_cs >= 0:
            reason = f"low change_score={best_cs:.2f} (corr={best_corr:.3f})"
        else:
            reason = f"near-duplicate (corr={best_corr:.3f})"

        print(
            f"  trim: drop hold @ {picks[drop] / fps:.2f}s "
            f"sharp={scores[drop]:.1f} ({reason})"
        )
        picks.pop(drop)
        scores.pop(drop)
        trimmed += 1

    return picks, scores, trimmed


def pick_in_range(
    frames: list,
    smooth: np.ndarray,
    short_side: int,
    lo: int,
    hi: int,
) -> int | None:
    if hi <= lo:
        return None
    best_i, best = None, -1e18
    for i in range(lo, hi):
        score = (
            sharpness_normalized(frames[i], short_side)
            - float(smooth[i]) * 1.5
            - falling_penalty(frames[i], short_side) * 0.6
        )
        if score > best:
            best, best_i = score, i
    return best_i


def pick_after_flip(
    frames: list,
    smooth: np.ndarray,
    short_side: int,
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
        span = end - start
        lo = start + int(span * 0.2)
        hi = end - int(span * 0.1)
        if hi <= lo:
            lo, hi = start, end
        return int(lo + np.argmin(smooth[lo:hi]))

    win_end = min(end, settled + max(2, int(fps * search_window)))
    return pick_in_range(frames, smooth, short_side, settled, win_end)


def pick_initial(
    frames: list,
    smooth: np.ndarray,
    short_side: int,
    fps: float,
    first_peak: int,
) -> int | None:
    hi = max(1, first_peak - int(fps * 0.05))
    return pick_in_range(frames, smooth, short_side, 0, hi)


def similar(
    frames: list,
    a: int,
    b: int,
    roi: tuple[int, int, int, int],
    corr_thr: float,
    lab_thr: float,
) -> bool:
    corr, dlab = pair_similarity(frames, a, b, roi)
    return corr >= corr_thr and dlab <= lab_thr


def change_score(
    frames: list,
    a: int,
    b: int,
    roi: tuple[int, int, int, int],
    smooth: np.ndarray,
    peak_ref: float,
) -> tuple[float, float, float, float]:
    """Motion × appearance delta between two holds.

    Returns (score, motion_norm, appearance, hist_corr).
    Low score ⇒ likely same garment (jiggle / re-hold).
    """
    corr, dlab = pair_similarity(frames, a, b, roi)
    lo, hi = (a, b) if a <= b else (b, a)
    if hi > lo and peak_ref > 0:
        motion = float(np.max(smooth[lo : hi + 1]))
        motion_norm = motion / peak_ref
    else:
        motion_norm = 1.0

    # appearance: 0 identical → 1 different
    app = (1.0 - corr) * 0.7 + min(dlab / 40.0, 1.0) * 0.3
    score = motion_norm * app
    return score, motion_norm, app, corr


def should_merge_consecutive(
    frames: list,
    a: int,
    b: int,
    roi: tuple[int, int, int, int],
    smooth: np.ndarray,
    peak_ref: float,
    corr_thr: float,
    lab_thr: float,
    change_gate: float,
    max_change_motion: float = 0.70,
) -> bool:
    """Merge if strict-similar, or low change_score with only weak intervening motion."""
    if similar(frames, a, b, roi, corr_thr, lab_thr):
        return True
    score, motion_norm, _app, _corr = change_score(
        frames, a, b, roi, smooth, peak_ref
    )
    # Strong flips between similar garments must NOT merge on change_score alone
    if motion_norm >= max_change_motion:
        return False
    return score < change_gate


def global_dedupe(
    frames: list,
    picks: list[int],
    roi: tuple[int, int, int, int],
    short_side: int,
    corr_thr: float,
    lab_thr: float,
) -> list[int]:
    """Keep sharpest frame per visual cluster (order-preserving)."""
    if not picks:
        return []

    scores = [sharpness_normalized(frames[i], short_side) for i in picks]
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

    return sorted(kept)


def relative_sharpness_floor(scores: list[float], median_ratio: float, abs_floor: float) -> float:
    """Per-video gate: max(abs_floor, median(scores) * ratio)."""
    if not scores:
        return abs_floor
    median = float(np.median(np.asarray(scores, dtype=np.float64)))
    return max(abs_floor, median * median_ratio)


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
    short_side = args.score_size
    print(f"{len(frames)} frames @ {fps:.2f} fps ({len(frames) / fps:.1f}s), {w}x{h}")
    print(f"Sharpness scored at short-side {short_side}px (full-res frames still saved).")

    if args.expected_count is not None and args.expected_count < 1:
        print("Error: --expected-count must be >= 1", file=sys.stderr)
        return 1

    print("Detecting flips (motion peaks) …")
    smooth = motion_curve(frames, roi, fps)
    peaks = find_flip_peaks(
        smooth, fps, peak_pct=args.peak_percentile, min_sep=args.min_peak_sep
    )
    print(f"Found {len(peaks)} flip peak(s).")
    if args.expected_count is not None:
        print(
            f"Expected count N={args.expected_count}: keep all peaks, "
            "then trim holds after sharpness gating (not by peak strength)."
        )
    else:
        print("No --expected-count set; using unconstrained detection.")

    candidates: list[int] = []
    if peaks:
        initial = pick_initial(frames, smooth, short_side, fps, peaks[0])
        if initial is not None:
            candidates.append(initial)
        for i, peak in enumerate(peaks):
            nxt = peaks[i + 1] if i + 1 < len(peaks) else None
            pick = pick_after_flip(
                frames,
                smooth,
                short_side,
                fps,
                peak,
                nxt,
                hold_pct=args.hold_percentile,
                search_window=args.search_window,
            )
            if pick is not None:
                candidates.append(pick)
    else:
        pick = pick_in_range(frames, smooth, short_side, 0, len(frames))
        if pick is not None:
            candidates.append(pick)

    consecutive: list[int] = []
    peak_ref = (
        float(np.median([smooth[p] for p in peaks]))
        if peaks
        else float(np.percentile(smooth, 70))
    )
    # Precompute adjacent change scores to set a per-video merge gate
    pair_change_scores: list[float] = []
    for i in range(len(candidates) - 1):
        cs, _m, _a, _c = change_score(
            frames, candidates[i], candidates[i + 1], roi, smooth, peak_ref
        )
        pair_change_scores.append(cs)
    if pair_change_scores:
        change_gate = max(
            args.min_change_score,
            float(np.median(pair_change_scores)) * args.change_median_ratio,
        )
    else:
        change_gate = args.min_change_score
    print(
        f"Change-score merge gate={change_gate:.2f} "
        f"(max(min={args.min_change_score}, "
        f"median_pair×{args.change_median_ratio}))"
    )

    for c in candidates:
        if consecutive and should_merge_consecutive(
            frames,
            consecutive[-1],
            c,
            roi,
            smooth,
            peak_ref,
            args.dedupe_corr,
            args.dedupe_lab,
            change_gate,
            max_change_motion=args.max_change_motion,
        ):
            if sharpness_normalized(frames[c], short_side) > sharpness_normalized(
                frames[consecutive[-1]], short_side
            ):
                consecutive[-1] = c
            continue
        consecutive.append(c)

    picks = global_dedupe(
        frames,
        consecutive,
        roi,
        short_side,
        corr_thr=args.dedupe_corr,
        lab_thr=args.dedupe_lab,
    )
    print(
        f"Candidates {len(candidates)} → {len(consecutive)} after consecutive "
        f"dedupe → {len(picks)} unique."
    )

    scores = [sharpness_normalized(frames[i], short_side) for i in picks]
    gate = relative_sharpness_floor(
        scores, args.sharpness_median_ratio, args.min_sharpness
    )
    median = float(np.median(scores)) if scores else 0.0
    print(
        f"Normalized sharpness median={median:.1f} → gate={gate:.1f} "
        f"(max(min={args.min_sharpness}, median×{args.sharpness_median_ratio}))"
    )

    gated_picks: list[int] = []
    gated_scores: list[float] = []
    sharpness_skipped = 0
    for frame_idx, score in zip(picks, scores, strict=True):
        if score < gate:
            sharpness_skipped += 1
            print(
                f"Hold @ {frame_idx / fps:.2f}s → skipped "
                f"(sharpness@{short_side}: {score:.1f} < {gate:.1f})"
            )
            continue
        gated_picks.append(frame_idx)
        gated_scores.append(score)

    trimmed = 0
    if args.expected_count is not None:
        before = len(gated_picks)
        if before > args.expected_count:
            print(
                f"Over N={args.expected_count} ({before} sharp holds) — "
                "trimming near-duplicates / lowest sharpness:"
            )
        gated_picks, gated_scores, trimmed = trim_to_expected_count(
            frames,
            gated_picks,
            gated_scores,
            roi,
            args.expected_count,
            fps,
            smooth=smooth,
            peak_ref=peak_ref,
            change_gate=change_gate,
        )
        if trimmed:
            print(
                f"Trimmed {trimmed} hold(s) to match N={args.expected_count} "
                f"({before} → {len(gated_picks)})."
            )
        if len(gated_picks) < args.expected_count:
            print(
                f"Warning: only {len(gated_picks)} item(s) after filtering; "
                f"expected N={args.expected_count}."
            )
    print()

    saved = 0
    skipped = sharpness_skipped + trimmed
    item_num = 0

    for frame_idx, score in zip(gated_picks, gated_scores, strict=True):
        item_num += 1
        filename = f"item_{item_num:03d}.jpg"
        ok = cv2.imwrite(
            str(args.output / filename),
            frames[frame_idx],
            [int(cv2.IMWRITE_JPEG_QUALITY), 95],
        )
        if not ok:
            skipped += 1
            print(f"Hold @ {frame_idx / fps:.2f}s → failed to write {filename}")
            continue

        (args.output / f"item_{item_num:03d}.sharpness.txt").write_text(
            f"{score:.1f}\n", encoding="utf-8"
        )
        saved += 1
        print(
            f"Flip→hold @ {frame_idx / fps:.2f}s → saved {filename} "
            f"(sharpness@{short_side}: {score:.1f})"
        )

    print("\n── Summary ──")
    print(f"Flip peaks detected:   {len(peaks)}")
    if args.expected_count is not None:
        print(f"Expected count N:      {args.expected_count}")
    print(f"Unique holds gated:    {len(gated_picks)}")
    print(f"Total saved:           {saved}")
    print(f"Total skipped:         {skipped}")
    print(f"Output folder:         {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
