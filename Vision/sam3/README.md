# SAM 3 video (isolated)

Separate env + code for Video2Catalog garment isolation via Hugging Face Transformers.

Docs: [SAM3 Video](https://huggingface.co/docs/transformers/en/model_doc/sam3_video)

## Why isolated

`facebook/sam3` needs a heavy stack (recent `torch` + `transformers`) that should not collide with the FastAPI app deps. Keep this folder self-contained.

## Model note

| Checkpoint | Use here? |
|---|---|
| `facebook/sam3` | Yes — HF `Sam3VideoModel` / `Sam3VideoProcessor` |
| `facebook/sam3.1` | Not via Transformers yet (Meta repo / multiplex). Fallback later if needed. |

## Setup

```bash
cd Vision/sam3
./setup_env.sh
source .venv/bin/activate
```

**Gated model (required before first run):**

1. `hf auth login` (browser login is fine)
2. Open https://huggingface.co/facebook/sam3 while logged in → **accept the license / request access**
3. Verify: `hf auth whoami` (should show your username)
4. If you still get 403, your account is not approved yet — wait or use another HF account that has access

Put a short supplier clip in `data/` (gitignored), or use the sample:

```bash
cp ../sample_video/Sample-video-mp4.m4v data/
```

## Run

```bash
source .venv/bin/activate
python run_video.py data/Sample-video-mp4.m4v --max-frames 50
# optional lower res for memory: --image-size 560
# custom prompts: --prompts jacket dress jeans
```

Writes `outputs/tracks.json` (masks omitted from JSON). Prints a short summary of unique item IDs per prompt.

## Export best full frames (coarse → refine)

**Time-optimized flow:** SAM only needs a coarse pass to find *when* each item appears.
Then export searches a local raw-video window around each slot for a cleaner frame
(sharp / low clutter / settled) — **no extra SAM**.

```bash
# 1) Coarse detect (~30 SAM frames ≈ a few minutes, not 15)
python run_video.py data/Sample-video-mp4.m4v --max-frames 30 --prompts jacket coat

# 2) Split into target_items + refine best full frame locally
python export_crops.py --target-items 15 --hand-region top-right --out outputs/frames
```

Optional refine knobs:
- `--refine-half-window 24` — wider local search
- `--refine-step 1` — every source frame in the window (slower, cleaner)
- `--no-refine` — only use coarse tracked frames

`--hand-region` options: `top-right` (default), `top-left`, `top`, `bottom-right`, `bottom-left`, `bottom`, `right`, `left`.

If two neighbors still look identical, raise merge sensitivity:

```bash
python export_crops.py --target-items 15 --hand-region top-right --similarity-threshold 0.28
```

Then describe with VLM:

```bash
cd ../vlm && source .venv/bin/activate
python describe_crops.py ../sam3/outputs/frames --out outputs/listings_frames.json
```

## Layout

| Path | Role |
|---|---|
| `setup_env.sh` | Create `.venv` + install `requirements.txt` |
| `run_video.py` | Load video → text prompts → SAM 3 track → JSON |
| `garment_track.py` | Shared `GarmentTrack` interface |
| `prompts.py` | Default garment noun prompts |
| `data/` | Local videos (not committed) |
| `outputs/` | Run artifacts (not committed) |

## Still out of scope here

Best-frame pick, cutouts, dedupe, and VLM listings stay downstream of this tracker.
