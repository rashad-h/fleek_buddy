"""Export one full best frame per garment for sequential rack-pass videos.

Change policy:
- Always split toward ``--target-items`` (known item count).
- New item when appearance changes, OR hand/hanger motion in ``--hand-region``.
- Best frame in each slot = sharpest settled view (least blur).
- Full frames only (no crops).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import TypedDict

import cv2
import numpy as np
from PIL import Image

from run_video import load_video_frames

# Where the hand usually grabs hangers. Varies by camera / supplier habit.
HAND_REGIONS = (
    "top-right",
    "top-left",
    "top",
    "bottom-right",
    "bottom-left",
    "bottom",
    "right",
    "left",
)


class BandBox(TypedDict):
    y0: float
    y1: float
    x0: float
    x1: float


HAND_BANDS: dict[str, BandBox] = {
    "top-right": {"y0": 0.0, "y1": 0.32, "x0": 0.30, "x1": 1.0},
    "top-left": {"y0": 0.0, "y1": 0.32, "x0": 0.0, "x1": 0.70},
    "top": {"y0": 0.0, "y1": 0.32, "x0": 0.0, "x1": 1.0},
    "bottom-right": {"y0": 0.68, "y1": 1.0, "x0": 0.30, "x1": 1.0},
    "bottom-left": {"y0": 0.68, "y1": 1.0, "x0": 0.0, "x1": 0.70},
    "bottom": {"y0": 0.68, "y1": 1.0, "x0": 0.0, "x1": 1.0},
    "right": {"y0": 0.0, "y1": 1.0, "x0": 0.55, "x1": 1.0},
    "left": {"y0": 0.0, "y1": 1.0, "x0": 0.0, "x1": 0.45},
}


def hand_band_pixels(rgb: np.ndarray, hand_region: str) -> np.ndarray:
    band = HAND_BANDS[hand_region]
    h, w = rgb.shape[:2]
    y0, y1 = int(h * band["y0"]), int(h * band["y1"])
    x0, x1 = int(w * band["x0"]), int(w * band["x1"])
    return rgb[y0:y1, x0:x1]


def resolve_video_path(payload: dict, tracks_path: Path) -> Path:
    video_path = Path(payload["video"])
    if video_path.is_absolute() and video_path.exists():
        return video_path
    for path in (Path.cwd() / video_path, tracks_path.parent.parent / video_path):
        if path.exists():
            return path.resolve()
    raise SystemExit(f"Video not found: {video_path}")


def load_frames_for_tracks(payload: dict, video_path: Path) -> np.ndarray:
    n_frames = int(payload["summary"]["frames"])
    max_frames_requested = payload.get("max_frames_requested")
    candidates: list[int | None] = []
    if max_frames_requested is not None:
        candidates.append(int(max_frames_requested))
    candidates.extend([n_frames, 50, 60, 80, 100, None])

    for request_n in dict.fromkeys(candidates):
        loaded, _ = load_video_frames(video_path, max_frames=request_n)
        if len(loaded) == n_frames:
            return loaded
    raise SystemExit(f"Could not reload {n_frames} frames for export.")


def skin_ratio(rgb: np.ndarray, hand_region: str) -> float:
    """Fraction of skin-like pixels in the configured hand band."""
    band = hand_band_pixels(rgb, hand_region)
    if band.size == 0:
        return 0.0
    ycrcb = cv2.cvtColor(band, cv2.COLOR_RGB2YCrCb)
    mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    return float(mask.mean() / 255.0)


def region_motion(prev: np.ndarray, curr: np.ndarray, hand_region: str) -> float:
    """Optical-flow magnitude in the configured hand/hanger band."""
    band_a = hand_band_pixels(prev, hand_region)
    band_b = hand_band_pixels(curr, hand_region)
    if band_a.size == 0 or band_b.size == 0:
        return 0.0
    gray_a = cv2.cvtColor(band_a, cv2.COLOR_RGB2GRAY)
    gray_b = cv2.cvtColor(band_b, cv2.COLOR_RGB2GRAY)
    # Farneback needs matching shapes.
    if gray_a.shape != gray_b.shape:
        h = min(gray_a.shape[0], gray_b.shape[0])
        w = min(gray_a.shape[1], gray_b.shape[1])
        gray_a = gray_a[:h, :w]
        gray_b = gray_b[:h, :w]
    flow = cv2.calcOpticalFlowFarneback(
        gray_a, gray_b, None, 0.5, 3, 15, 3, 5, 1.2, 0
    )
    mag = np.sqrt(flow[..., 0] ** 2 + flow[..., 1] ** 2)
    return float(mag.mean())


def center_hist(rgb: np.ndarray) -> np.ndarray:
    h, w = rgb.shape[:2]
    crop = rgb[int(h * 0.12) : int(h * 0.88), int(w * 0.18) : int(w * 0.82)]
    hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
    cv2.normalize(hist, hist)
    return hist.flatten().astype(np.float32)


def center_sharpness(rgb: np.ndarray) -> float:
    """Higher = less blur / more detail on the garment."""
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    crop = gray[int(h * 0.18) : int(h * 0.82), int(w * 0.22) : int(w * 0.78)]
    return float(cv2.Laplacian(crop, cv2.CV_64F).var())


def flip_scores(
    frames: np.ndarray, hand_region: str
) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame change score + sharpness. Index 0 is unused for change."""
    n = len(frames)
    skins = [skin_ratio(frame, hand_region) for frame in frames]
    hists = [center_hist(frame) for frame in frames]
    sharp = np.array([center_sharpness(frame) for frame in frames], dtype=np.float64)

    app = np.zeros(n, dtype=np.float64)
    mot = np.zeros(n, dtype=np.float64)
    dskin = np.zeros(n, dtype=np.float64)
    for i in range(1, n):
        app[i] = float(
            cv2.compareHist(hists[i - 1], hists[i], cv2.HISTCMP_BHATTACHARYYA)
        )
        mot[i] = region_motion(frames[i - 1], frames[i], hand_region)
        dskin[i] = abs(skins[i] - skins[i - 1])

    mot_n = np.clip(mot / (np.percentile(mot[1:], 85) + 1e-6), 0.0, 2.0)
    score = 1.0 * app + 0.35 * mot_n + 8.0 * dskin
    alike = app < 0.28
    score = score + alike * (0.45 * mot_n + 10.0 * dskin)
    return score, sharp


def peak_boundaries(
    score: np.ndarray,
    *,
    min_distance: int,
    threshold: float,
    target_items: int,
) -> list[int]:
    """Return [0, peak..., n] slot boundaries for exactly ``target_items`` slots."""
    n = len(score)
    need = max(1, target_items) - 1
    order = np.argsort(score)[::-1]
    peaks: list[int] = []
    for idx in order:
        i = int(idx)
        if i == 0:
            continue
        if score[i] < threshold:
            break
        if all(abs(i - p) >= min_distance for p in peaks):
            peaks.append(i)

    peaks = sorted(peaks)

    while len(peaks) < need:
        points = [0, *peaks, n]
        best_peak = None
        best_gap_len = 0
        for a, b in zip(points[:-1], points[1:], strict=True):
            gap = b - a
            if gap < 2 * min_distance:
                continue
            lo = a + min_distance
            hi = b - min_distance
            if hi <= lo:
                continue
            local = int(lo + np.argmax(score[lo:hi]))
            if gap > best_gap_len:
                best_gap_len = gap
                best_peak = local
        if best_peak is None:
            break
        peaks.append(best_peak)
        peaks = sorted(peaks)

    if len(peaks) > need:
        kept: list[int] = []
        for i in sorted(peaks, key=lambda p: score[p], reverse=True):
            if all(abs(i - k) >= min_distance for k in kept):
                kept.append(i)
            if len(kept) >= need:
                break
        peaks = sorted(kept)
        while len(peaks) < need:
            points = [0, *peaks, n]
            best_peak = None
            best_gap_len = 0
            for a, b in zip(points[:-1], points[1:], strict=True):
                if b - a < 2 * min_distance:
                    continue
                lo = a + min_distance
                hi = b - min_distance
                if hi <= lo:
                    continue
                local = int(lo + np.argmax(score[lo:hi]))
                if b - a > best_gap_len:
                    best_gap_len = b - a
                    best_peak = local
            if best_peak is None:
                break
            peaks.append(best_peak)
            peaks = sorted(peaks)

    return [0, *sorted(peaks), n]


def merge_short_slots(bounds: list[int], min_len: int = 2) -> list[int]:
    """Merge 1-frame slots into the following slot (common at video start)."""
    if len(bounds) < 3:
        return bounds
    merged = [bounds[0]]
    i = 0
    while i < len(bounds) - 1:
        start, end = bounds[i], bounds[i + 1]
        if end - start < min_len and i + 2 < len(bounds):
            # skip this boundary; extend into next
            i += 1
            continue
        merged.append(end)
        i += 1
    if merged[-1] != bounds[-1]:
        merged.append(bounds[-1])
    # de-dupe while preserving order
    out: list[int] = []
    for b in merged:
        if not out or b != out[-1]:
            out.append(b)
    return out


def box_area(box: list[float]) -> float:
    return max(0.0, (box[2] - box[0]) * (box[3] - box[1]))


def box_iou(a: list[float], b: list[float]) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    inter = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    if inter <= 0:
        return 0.0
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def frame_tracks(payload: dict, frame_idx: int) -> list[dict]:
    return payload.get("frames", {}).get(str(frame_idx), [])


def isolation_score(tracks: list[dict], frame_h: int, frame_w: int) -> float:
    """Higher when one large centered garment dominates and neighbors overlap less."""
    if not tracks:
        return 0.0
    boxes = sorted(
        [t["bounding_box"] for t in tracks if box_area(t["bounding_box"]) > 80_000],
        key=box_area,
        reverse=True,
    )
    if not boxes:
        return 0.0
    main = boxes[0]
    area_norm = min(1.0, box_area(main) / (frame_h * frame_w * 0.45))
    cx = (main[0] + main[2]) / 2.0
    cy = (main[1] + main[3]) / 2.0
    center = max(
        0.0,
        1.0
        - 0.5
        * (
            abs(cx - frame_w / 2) / max(1.0, frame_w / 2)
            + abs(cy - frame_h / 2) / max(1.0, frame_h / 2)
        ),
    )
    # Penalize heavy overlap with the next-largest box (stacked / occluded).
    neighbor_pen = 0.0
    if len(boxes) > 1:
        neighbor_pen = box_iou(main, boxes[1])
    # Extra large boxes beyond the main one ⇒ crowded rack in view.
    crowd_pen = min(1.0, max(0, len(boxes) - 1) / 4.0)
    return 0.45 * area_norm + 0.35 * center + 0.20 * (1.0 - neighbor_pen) - 0.15 * crowd_pen


def best_frame_in_slot(
    frames: np.ndarray,
    sharp: np.ndarray,
    payload: dict,
    start: int,
    end: int,
    *,
    prev_hist: np.ndarray | None,
) -> tuple[int, float]:
    """Pick least-blurry, least-occluded frame, unlike the previous item."""
    idxs = list(range(start, end))
    frame_h, frame_w = frames.shape[1], frames.shape[2]
    settle_from = start + max(0, (end - start) // 4)
    sharp_max = float(max(sharp[start:end])) if end > start else 1.0

    best_i = idxs[0]
    best_score = -1e9
    for i in idxs:
        iso = isolation_score(frame_tracks(payload, i), frame_h, frame_w)
        sharp_n = float(sharp[i]) / (sharp_max + 1e-6)
        settle = 0.08 if i >= settle_from else 0.0
        # Prefer frames that look different from the previous kept item.
        novelty = 0.0
        if prev_hist is not None:
            dist = float(
                cv2.compareHist(prev_hist, center_hist(frames[i]), cv2.HISTCMP_BHATTACHARYYA)
            )
            novelty = min(1.0, dist / 0.45)
        # Weighted: isolation + sharpness + novelty vs previous piece.
        score = 0.40 * iso + 0.30 * sharp_n + 0.25 * novelty + settle
        if score > best_score:
            best_score = score
            best_i = i
    return best_i, best_score


def peripheral_clutter(rgb: np.ndarray) -> float:
    """Higher when side/edge regions look busy (stacked garments peeking in)."""
    h, w = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 60, 140)
    center = edges[int(h * 0.2) : int(h * 0.8), int(w * 0.25) : int(w * 0.75)]
    sides = np.concatenate(
        [
            edges[int(h * 0.15) : int(h * 0.85), : int(w * 0.18)].ravel(),
            edges[int(h * 0.15) : int(h * 0.85), int(w * 0.82) :].ravel(),
        ]
    )
    c = float(center.mean()) + 1e-6
    s = float(sides.mean())
    return min(1.5, s / c)


def local_motion(prev: np.ndarray | None, curr: np.ndarray, nxt: np.ndarray | None) -> float:
    """Cheap motion estimate; high = mid-flip blur."""
    gray = cv2.cvtColor(curr, cv2.COLOR_RGB2GRAY)
    scores: list[float] = []
    for other in (prev, nxt):
        if other is None:
            continue
        g2 = cv2.cvtColor(other, cv2.COLOR_RGB2GRAY)
        diff = cv2.absdiff(gray, g2)
        scores.append(float(diff.mean()) / 255.0)
    return float(np.mean(scores)) if scores else 0.0


def score_candidate_frame(
    rgb: np.ndarray,
    *,
    prev_rgb: np.ndarray | None,
    next_rgb: np.ndarray | None,
    prev_hist: np.ndarray | None,
    hand_region: str,
) -> float:
    """OpenCV-only score: sharp, settled, low clutter, unlike previous item."""
    sharp = center_sharpness(rgb)
    sharp_n = min(1.0, sharp / 60.0)
    clutter = peripheral_clutter(rgb)
    motion = local_motion(prev_rgb, rgb, next_rgb)
    hand = skin_ratio(rgb, hand_region)
    # Prefer some hand presence (item being held) but not a blurry mid-grab.
    hand_pref = 1.0 - abs(hand - 0.05) / 0.12
    hand_pref = float(np.clip(hand_pref, 0.0, 1.0))
    novelty = 0.5
    if prev_hist is not None:
        dist = float(cv2.compareHist(prev_hist, center_hist(rgb), cv2.HISTCMP_BHATTACHARYYA))
        novelty = min(1.0, dist / 0.45)
    return (
        0.35 * sharp_n
        + 0.25 * (1.0 - min(1.0, clutter))
        + 0.20 * (1.0 - min(1.0, motion * 4.0))
        + 0.10 * hand_pref
        + 0.10 * novelty
    )


def read_source_range(
    video_path: Path,
    start_src: int,
    end_src: int,
    *,
    step: int,
) -> tuple[list[int], list[np.ndarray]]:
    """Decode frames in [start_src, end_src] inclusive."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise SystemExit(f"Could not open video: {video_path}")
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 10_000
    start = max(0, start_src)
    end = min(end_src, total - 1)
    indices = list(range(start, end + 1, max(1, step)))
    frames: list[np.ndarray] = []
    kept: list[int] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, bgr = cap.read()
        if not ok:
            continue
        frames.append(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        kept.append(idx)
    cap.release()
    return kept, frames


def refine_best_around_slot(
    video_path: Path,
    source_indices: list[int],
    coarse_start: int,
    coarse_end: int,
    *,
    hand_region: str,
    prev_hist: np.ndarray | None,
    prev_src: int | None,
    half_window: int,
    step: int,
) -> tuple[np.ndarray, int, float]:
    """Search raw video near the coarse slot for a cleaner full frame."""
    src_lo = source_indices[min(coarse_start, len(source_indices) - 1)]
    src_hi = source_indices[min(coarse_end - 1, len(source_indices) - 1)]
    if src_hi < src_lo:
        src_lo, src_hi = src_hi, src_lo

    # Stay mostly inside the slot; pad a little to catch a cleaner nearby frame.
    pad = max(4, half_window // 2)
    start_src = src_lo - pad
    end_src = src_hi + pad
    if prev_src is not None:
        start_src = max(start_src, prev_src + 1)

    src_ids, local_frames = read_source_range(
        video_path, start_src, end_src, step=step
    )
    if not local_frames:
        # Fallback to exact mid coarse frame.
        mid = (coarse_start + coarse_end - 1) // 2
        mid = min(max(mid, 0), len(source_indices) - 1)
        src_ids, local_frames = read_source_range(
            video_path, source_indices[mid], source_indices[mid], step=1
        )
    if not local_frames:
        raise SystemExit(f"No frames decoded for slot covering source {src_lo}-{src_hi}")

    best_i = 0
    best_score = -1e9
    for i, rgb in enumerate(local_frames):
        prev_rgb = local_frames[i - 1] if i > 0 else None
        next_rgb = local_frames[i + 1] if i + 1 < len(local_frames) else None
        s = score_candidate_frame(
            rgb,
            prev_rgb=prev_rgb,
            next_rgb=next_rgb,
            prev_hist=prev_hist,
            hand_region=hand_region,
        )
        # Soft preference for frames inside the original slot range.
        if src_lo <= src_ids[i] <= src_hi:
            s += 0.05
        if s > best_score:
            best_score = s
            best_i = i
    return local_frames[best_i], src_ids[best_i], float(best_score)


def merge_similar_adjacent_slots(
    bounds: list[int],
    frames: np.ndarray,
    sharp: np.ndarray,
    payload: dict,
    score: np.ndarray,
    *,
    target_items: int,
    min_distance: int,
    similarity_threshold: float = 0.25,
) -> list[int]:
    """Merge adjacent slots whose best frames look like the same garment, then refill."""
    if len(bounds) < 3:
        return bounds

    working = list(bounds)
    while True:
        slots = list(zip(working[:-1], working[1:], strict=True))
        bests: list[tuple[int, np.ndarray]] = []
        prev_hist: np.ndarray | None = None
        for start, end in slots:
            idx, _ = best_frame_in_slot(
                frames, sharp, payload, start, end, prev_hist=prev_hist
            )
            hist = center_hist(frames[idx])
            bests.append((idx, hist))
            prev_hist = hist

        merge_at: int | None = None
        closest = 1e9
        for i in range(len(bests) - 1):
            dist = float(
                cv2.compareHist(bests[i][1], bests[i + 1][1], cv2.HISTCMP_BHATTACHARYYA)
            )
            if dist < similarity_threshold and dist < closest:
                closest = dist
                merge_at = i + 1
        if merge_at is None:
            break
        del working[merge_at]

    need_bounds = target_items + 1
    while len(working) < need_bounds:
        best_peak = None
        best_gap = 0.0
        for a, b in zip(working[:-1], working[1:], strict=True):
            if b - a < 2 * min_distance:
                continue
            lo = a + min_distance
            hi = b - min_distance
            if hi <= lo:
                continue
            segment = score[lo:hi].copy()
            order = np.argsort(segment)[::-1]
            for rel in order[:12]:
                local = int(lo + rel)
                # Require a real appearance jump at the cut (not hand-only noise).
                jump = float(
                    cv2.compareHist(
                        center_hist(frames[max(a, local - 1)]),
                        center_hist(frames[min(b - 1, local)]),
                        cv2.HISTCMP_BHATTACHARYYA,
                    )
                )
                if jump < max(0.12, similarity_threshold * 0.5):
                    continue

                left_idx, _ = best_frame_in_slot(
                    frames, sharp, payload, a, local, prev_hist=None
                )
                right_idx, _ = best_frame_in_slot(
                    frames, sharp, payload, local, b, prev_hist=None
                )
                # Compare settled views: sharpest frame in each half.
                left_sharp = max(range(a, local), key=lambda i: float(sharp[i]))
                right_sharp = max(range(local, b), key=lambda i: float(sharp[i]))
                dist = float(
                    cv2.compareHist(
                        center_hist(frames[left_sharp]),
                        center_hist(frames[right_sharp]),
                        cv2.HISTCMP_BHATTACHARYYA,
                    )
                )
                if dist < similarity_threshold:
                    continue
                gap_score = (b - a) * (0.35 + float(score[local])) * (0.3 + jump + dist)
                if gap_score > best_gap:
                    best_gap = gap_score
                    best_peak = local
                break
        if best_peak is None or best_peak in working:
            break
        working.append(best_peak)
        working = sorted(working)

    # Final safety: merge similar neighbors again (no refill) so we never ship dups.
    while True:
        slots = list(zip(working[:-1], working[1:], strict=True))
        bests = []
        prev_hist = None
        for start, end in slots:
            idx, _ = best_frame_in_slot(
                frames, sharp, payload, start, end, prev_hist=prev_hist
            )
            hist = center_hist(frames[idx])
            bests.append(hist)
            prev_hist = hist
        merge_at = None
        closest = 1e9
        for i in range(len(bests) - 1):
            dist = float(cv2.compareHist(bests[i], bests[i + 1], cv2.HISTCMP_BHATTACHARYYA))
            if dist < similarity_threshold and dist < closest:
                closest = dist
                merge_at = i + 1
        if merge_at is None:
            break
        del working[merge_at]

    return working


def export_best_frames(
    tracks_path: Path,
    out_dir: Path,
    *,
    target_items: int,
    hand_region: str = "top-right",
    min_distance: int = 3,
    threshold: float = 0.48,
    min_slot_frames: int = 1,
    similarity_threshold: float = 0.25,
    refine: bool = True,
    refine_half_window: int = 18,
    refine_step: int = 2,
) -> dict:
    if target_items < 1:
        raise SystemExit("--target-items must be >= 1")
    if hand_region not in HAND_BANDS:
        raise SystemExit(f"Unknown --hand-region {hand_region!r}. Choose from {HAND_REGIONS}")

    payload = json.loads(tracks_path.read_text())
    video_path = resolve_video_path(payload, tracks_path)
    frames = load_frames_for_tracks(payload, video_path)
    score, sharp = flip_scores(frames, hand_region)

    bounds = peak_boundaries(
        score,
        min_distance=min_distance,
        threshold=threshold,
        target_items=target_items,
    )
    if min_slot_frames > 1:
        bounds = merge_short_slots(bounds, min_len=min_slot_frames)

    bounds = merge_similar_adjacent_slots(
        bounds,
        frames,
        sharp,
        payload,
        score,
        target_items=target_items,
        min_distance=min_distance,
        similarity_threshold=similarity_threshold,
    )

    source_indices = payload.get("source_frame_indices")
    if source_indices is None or len(source_indices) != len(frames):
        # Fallback: assume uniform indices matching loaded frames.
        source_indices = list(range(len(frames)))
    else:
        source_indices = [int(i) for i in source_indices]

    out_dir.mkdir(parents=True, exist_ok=True)
    items: list[dict] = []
    prev_hist: np.ndarray | None = None
    prev_src: int | None = None

    for slot_id, (start, end) in enumerate(zip(bounds[:-1], bounds[1:], strict=True)):
        coarse_idx, coarse_quality = best_frame_in_slot(
            frames, sharp, payload, start, end, prev_hist=prev_hist
        )

        if refine:
            best_rgb, src_idx, quality = refine_best_around_slot(
                video_path,
                source_indices,
                start,
                end,
                hand_region=hand_region,
                prev_hist=prev_hist,
                prev_src=prev_src,
                half_window=refine_half_window,
                step=refine_step,
            )
            # Prefer refined frame unless it collapses onto the previous item.
            refined_hist = center_hist(best_rgb)
            if prev_hist is not None:
                dist = float(
                    cv2.compareHist(prev_hist, refined_hist, cv2.HISTCMP_BHATTACHARYYA)
                )
                if dist < similarity_threshold:
                    best_rgb = frames[coarse_idx]
                    src_idx = source_indices[coarse_idx]
                    if prev_src is not None and src_idx <= prev_src:
                        src_idx = prev_src + 1
                    quality = coarse_quality
                    refined_hist = center_hist(best_rgb)
            path = out_dir / f"item_{slot_id:03d}_src{src_idx:04d}_full.png"
            Image.fromarray(best_rgb).save(path)
            prev_hist = refined_hist
            prev_src = int(src_idx)
            items.append(
                {
                    "slot_id": slot_id,
                    "coarse_frame_index": coarse_idx,
                    "source_frame_index": int(src_idx),
                    "frame_start": start,
                    "frame_end": end - 1,
                    "sharpness": float(center_sharpness(best_rgb)),
                    "quality_score": float(quality),
                    "isolation": float(
                        isolation_score(
                            frame_tracks(payload, coarse_idx),
                            frames.shape[1],
                            frames.shape[2],
                        )
                    ),
                    "flip_score_at_start": float(score[start]),
                    "path": str(path),
                }
            )
        else:
            path = out_dir / f"item_{slot_id:03d}_f{coarse_idx:03d}_full.png"
            Image.fromarray(frames[coarse_idx]).save(path)
            prev_hist = center_hist(frames[coarse_idx])
            prev_src = int(source_indices[coarse_idx])
            items.append(
                {
                    "slot_id": slot_id,
                    "frame_index": coarse_idx,
                    "source_frame_index": int(source_indices[coarse_idx]),
                    "frame_start": start,
                    "frame_end": end - 1,
                    "sharpness": float(sharp[coarse_idx]),
                    "quality_score": float(coarse_quality),
                    "isolation": float(
                        isolation_score(
                            frame_tracks(payload, coarse_idx),
                            frames.shape[1],
                            frames.shape[2],
                        )
                    ),
                    "flip_score_at_start": float(score[start]),
                    "path": str(path),
                }
            )

    # Drop near-duplicate adjacent exports after refine.
    filtered: list[dict] = []
    prev_h: np.ndarray | None = None
    for item in items:
        hist = center_hist(np.array(Image.open(item["path"]).convert("RGB")))
        if prev_h is not None:
            dist = float(cv2.compareHist(prev_h, hist, cv2.HISTCMP_BHATTACHARYYA))
            if dist < similarity_threshold:
                continue
        filtered.append(item)
        prev_h = hist

    # If refine/dedupe dropped below target, keep original items (better than silent loss).
    if len(filtered) >= max(1, target_items - 2):
        # Re-number slot ids / filenames for contiguous output.
        final_items: list[dict] = []
        for new_id, item in enumerate(filtered):
            old_path = Path(item["path"])
            new_name = f"item_{new_id:03d}_src{int(item['source_frame_index']):04d}_full.png"
            new_path = out_dir / new_name
            if old_path != new_path:
                if new_path.exists():
                    new_path.unlink()
                old_path.rename(new_path)
            item = {**item, "slot_id": new_id, "path": str(new_path)}
            final_items.append(item)
        items = final_items

    manifest = {
        "mode": "coarse_detect_local_refine",
        "policy": (
            "Coarse SAM frames find ~target_items temporal slots. "
            "Then search a local raw-video window around each slot for the "
            "sharpest / least-cluttered full frame (no extra SAM)."
        ),
        "video": str(video_path),
        "tracks": str(tracks_path),
        "params": {
            "target_items": target_items,
            "hand_region": hand_region,
            "min_distance": min_distance,
            "threshold": threshold,
            "min_slot_frames": min_slot_frames,
            "similarity_threshold": similarity_threshold,
            "refine": refine,
            "refine_half_window": refine_half_window,
            "refine_step": refine_step,
        },
        "n_frames": len(frames),
        "n_items": len(items),
        "boundaries": bounds,
        "items": items,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Coarse item detect from tracks.json, then refine best full frames "
            "in a local video window (fast + cleaner)."
        )
    )
    parser.add_argument("--tracks", type=Path, default=Path("outputs/tracks.json"))
    parser.add_argument("--out", type=Path, default=Path("outputs/frames"))
    parser.add_argument(
        "--target-items",
        type=int,
        required=True,
        help="Known number of garments in the video (required)",
    )
    parser.add_argument(
        "--hand-region",
        choices=HAND_REGIONS,
        default="top-right",
        help="Where the hand enters / grabs hangers (varies by video)",
    )
    parser.add_argument(
        "--min-distance",
        type=int,
        default=3,
        help="Minimum coarse frames between item changes",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.48,
        help="Minimum flip score before gap-fill toward target-items",
    )
    parser.add_argument("--min-slot-frames", type=int, default=1)
    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=0.25,
        help="Merge/drop adjacent items if hist distance is below this",
    )
    parser.add_argument(
        "--no-refine",
        action="store_true",
        help="Only use coarse tracked frames (skip local video search)",
    )
    parser.add_argument(
        "--refine-half-window",
        type=int,
        default=18,
        help="Source frames left/right of each coarse slot to search",
    )
    parser.add_argument(
        "--refine-step",
        type=int,
        default=2,
        help="Stride inside the local refine window (1 = every frame)",
    )
    args = parser.parse_args()

    if not args.tracks.exists():
        raise SystemExit(f"Tracks file not found: {args.tracks}")

    manifest = export_best_frames(
        args.tracks,
        args.out,
        target_items=args.target_items,
        hand_region=args.hand_region,
        min_distance=args.min_distance,
        threshold=args.threshold,
        min_slot_frames=args.min_slot_frames,
        similarity_threshold=args.similarity_threshold,
        refine=not args.no_refine,
        refine_half_window=args.refine_half_window,
        refine_step=args.refine_step,
    )

    keep = {Path(item["path"]).name for item in manifest["items"]}
    for old in args.out.glob("item_*.png"):
        if old.name not in keep:
            old.unlink()

    print(
        f"Exported {manifest['n_items']} full frames → {args.out} "
        f"(target={args.target_items}, hand={args.hand_region}, "
        f"refine={not args.no_refine})"
    )
    for item in manifest["items"]:
        src = item.get("source_frame_index")
        print(
            f"  item {item['slot_id']:02d}  coarse {item['frame_start']:02d}-{item['frame_end']:02d}  "
            f"src={src}  sharp={item['sharpness']:.1f}  q={item['quality_score']:.2f}  {item['path']}"
        )


if __name__ == "__main__":
    main()
