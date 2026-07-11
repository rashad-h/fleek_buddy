# Motion-hold / flip-peak experiment

Works across sample clips with different resolutions by **standardizing sharpness**.

## Sharpness standardization

1. Resize a copy to short-side **720px** (scoring only — saved JPEGs stay full-res)
2. Laplacian variance on the garment ROI of that copy
3. Per-video gate: `max(5.0, median(candidate_scores) * 0.4)`

So soft phone clips and sharp high-res clips share one rule without a brittle absolute threshold.

## Setup

```bash
cd Vision/pySceneDetect
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Extract + gallery

```bash
python extract.py --video ../sample_video/Sample-video-mp4.m4v --output ./frames
python extract.py --video ../sample_video/Sample-video-mp4.m4v --output ./frames -N 15
python gallery.py --input ./frames
open frames/gallery.html
```

| Flag | Default | Role |
|------|---------|------|
| `-N` / `--expected-count` | unset | After gating, trim extras by low change_score / near-dup |
| `--score-size` | `720` | Short-side px for sharpness scoring |
| `--sharpness-median-ratio` | `0.4` | Keep if score ≥ median × ratio |
| `--min-sharpness` | `5` | Absolute floor on normalized score |
| `--change-median-ratio` | `0.45` | Merge if change_score < median×ratio |
| `--min-change-score` | `0.25` | Absolute floor for that merge gate |
| `--max-change-motion` | `0.70` | Change-score merge only if intervening motion below this × median peak |
| `--peak-percentile` | `70` | Motion peaks above this %ile = flips |
| `--min-peak-sep` | `0.42` | Min seconds between flips |
| `--dedupe-corr` | `0.97` | Strict hist merge |
| `--dedupe-lab` | `5` | Strict LAB merge |

`change_score = normalized_intervening_motion × appearance_delta`  
(appearance mixes hist corr + LAB). Low score ⇒ same garment re-hold / jiggle → merge.
