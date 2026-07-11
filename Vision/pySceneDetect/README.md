# Motion-hold / flip-peak experiment

Tuned for `Vision/sample_video/Sample-video-mp4.m4v` (~15 distinct garments).

## Approach

Soft continuous flips ≠ hard scene cuts. `extract.py` instead:

1. Detect **flip peaks** (motion spikes)
2. After each flip, wait for motion to settle, pick sharpest frame
3. Also keep the initial pre-first-flip hold
4. Dedupe near-identical consecutive holds (HSV hist + LAB distance)
5. Penalize frames where the previous garment is still falling (bottom blur)

## Setup

```bash
cd Vision/pySceneDetect
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Extract + gallery

```bash
python extract.py --video ../sample_video/Sample-video-mp4.m4v --output ./frames
python gallery.py --input ./frames
open frames/gallery.html
```

| Flag | Default | Role |
|------|---------|------|
| `--peak-percentile` | `70` | Motion peaks above this %ile = flips |
| `--min-peak-sep` | `0.42` | Min seconds between flips |
| `--dedupe-corr` | `0.97` | Merge only near-identical hist |
| `--dedupe-lab` | `5` | …and close mean LAB color |
| `--min-sharpness` | `28` | Reject soft frames |
