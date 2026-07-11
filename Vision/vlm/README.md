# VLM metadata (isolated)

Turn SAM 3 **full item frames** into structured listing attributes with **Gemini** or **Qwen** via LiteLLM.

## Setup

```bash
cd Vision/vlm
./setup_env.sh
cp .env.example .env   # if not already created
# add GEMINI_API_KEY=...  or  DASHSCOPE_API_KEY=...
source .venv/bin/activate
```

| Provider | Env key | Example model |
|---|---|---|
| Gemini (default) | `GEMINI_API_KEY` | `gemini/gemini-3.5-flash` |
| Qwen (DashScope) | `DASHSCOPE_API_KEY` | `dashscope/qwen-vl-max` |
| Qwen (OpenRouter) | `OPENROUTER_API_KEY` | `openrouter/qwen/qwen2.5-vl-72b-instruct` |

## Run

Point at SAM 3 `outputs/frames/` (full best frames per item):

```bash
# smoke test one image
python describe_crops.py ../sam3/outputs/frames --limit 1

# full folder
python describe_crops.py ../sam3/outputs/frames --out outputs/listings_frames.json

# force Qwen
python describe_crops.py ../sam3/outputs/frames --model dashscope/qwen-vl-max
```

The prompt tells the VLM to describe the **front-most garment** and ignore rack / hand / wall.

### Gemini free-tier note

Free tier is about **5 requests/minute**. The script defaults to `--sleep 13` for Gemini and waits/retries on 429. A 15-image run takes ~3–4 minutes.

Use **`gemini-3.5-flash`** (default). `gemini-2.5-flash` returns 404 for many new API keys.

## Output

`listings_frames.json` entries include:

**Listing**
- `category`, `subcategory`, `brand`, `brand_tier`
- `color_primary` / `color_secondary`, `pattern`, `visible_text`
- `condition_visible`, `defects_visible`, `defect_severity`
- `short_title`, `description`
- `confidence`, `needs_review`

**Negotiation (lean)**
- `talking_points` (≤3) — what the seller can cite
- `buyer_objection_risks` (≤3) — likely buyer pushback
- `suggested_stance` — `firm` / `balanced` / `flexible` (derived in code, not from Gemini)

Skipped on purpose (cost / unreliable from a single frame): size, era, seasonality, retail comps, exact prices.

## Layout

| Path | Role |
|---|---|
| `describe_crops.py` | CLI: folder of frames → JSON listings |
| `schema.py` | Pydantic attribute schema |
| `prompts.py` | System + multimodal user message (full-frame aware) |
| `.env` | Provider keys (not committed) |
