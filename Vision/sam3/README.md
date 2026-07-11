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
