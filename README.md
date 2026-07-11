# Fleek Buddy

A Fleek-style wholesale marketplace demo with two sides:

1. **Buyer marketplace** — you browse seeded (and merchant-published) bundles and
   haggle with an **LLM seller agent** in a real-time chat. Offers can cover the
   full lot or specific grades; the agent counters, holds firm, accepts, or
   walks away using confidential floors and stock.
2. **Merchant dashboard** (`/merchant`) — suppliers upload a haul video; the
   backend extracts garment frames, runs Gemini vision on each frame in
   parallel, builds one wholesale listing, and publishes it into the same
   buyer catalogue (with a full image gallery).

Judge-facing walkthrough: see [`DEMO.md`](./DEMO.md).

## Architecture

```
browser :3000 ──> ui (TanStack Start / Vite)
                    ├── /api proxy ──> backend :8000   (full Docker: make dev)
                    └── or VITE_API_URL ──> host :8000 (merchant: make dev-merchant
                                                        + make dev-backend-host)
                                          ├── Postgres :5432
                                          ├── LiteLLM ──> OpenRouter / Anthropic / OpenAI
                                          │                 (seller agent)
                                          └── Vision/ (host only)
                                                ├── pySceneDetect  → frames
                                                └── vlm (Gemini)   → per-garment JSON
```

| Area | Stack |
| --- | --- |
| `ui/` | TanStack Start + Query, Tailwind v4, shadcn/ui |
| `backend/` | FastAPI, async SQLAlchemy, Alembic, LiteLLM |
| `Vision/pySceneDetect/` | OpenCV scene / flip-hold extractor |
| `Vision/vlm/` | LiteLLM → Gemini for garment attributes |

## What we built (merchant + catalogue)

### End-to-end merchant pipeline

1. **Upload or sample video** on `/merchant` (optional expected item count).
2. **Extract frames** via `Vision/pySceneDetect/extract.py` (`-N` only when a
   count is provided; otherwise unconstrained).
3. **Describe every frame in parallel** with Gemini
   (`Vision/vlm/describe_crops.py --workers N`).
4. **Bundle summary** — local synthesis from per-item JSON (instant; avoids a
   second Gemini hang). Optional Gemini polish behind `MERCHANT_SUMMARY_LLM=1`.
5. **Review in the merchant UI** — live SSE progress, garment cards, summary.
6. **Publish** — one marketplace `Item` (`vendor_name=Video Catalog`) with:
   - listing copy from the summary
   - `image_url` + `image_urls` (all frames copied to `ui/public/merchant/{job_id}/`)
   - negotiable pricing, floors, and synthetic A/B `grades` for the seller agent

Job artifacts live under `backend/data/merchant_jobs/{job_id}/` (gitignored):
`video`, `frames/`, `listings.json`, `summary.json`, logs.

### Buyer gallery

Items expose `image_urls` (JSONB). The item detail page shows a thumbnail strip
when more than one image exists. Seeded listings get a one-element gallery;
published video lots include every extracted frame.

### Host vs Docker (important for merchant)

Merchant Vision tooling needs **macOS host venvs** (OpenCV / Gemini). The Docker
backend does **not** mount `Vision/`, so extraction fails there with paths like
`/Vision/pySceneDetect/extract.py`.

Use:

```bash
make setup-vision-envs   # once
make dev-merchant        # terminal 1: db + ui
make dev-backend-host    # terminal 2: API on host :8000
```

`docker-compose.yml` no longer makes `ui` depend on `backend`, so merchant mode
does not secretly restart the Docker API and steal port 8000.

### Seller agent env loading

The host API runs from `backend/`. Settings now load **both**
`backend/.env` and the monorepo root `.env` (where keys usually live). Without
that, LiteLLM fell back to `anthropic/claude-sonnet-5` with no key and the
agent replied *“Sorry, I lost my train of thought…”*.

Match `LLM_MODEL` to a configured key (this repo often uses OpenRouter).

## Quickstart (buyer marketplace only)

```bash
cp .env.example .env          # set OPENROUTER_API_KEY / ANTHROPIC_API_KEY / etc.
make dev                      # ui → http://localhost:3000, api → :8000/docs
make seed                     # second terminal: Seeded 9 bundles.
```

Migrations apply automatically when the backend container starts.

## Merchant quickstart

```bash
cp .env.example .env
# set GEMINI_API_KEY (required for per-frame VLM)
# set LLM_* keys (required for buyer haggling after publish)

make setup-vision-envs
# also put GEMINI_API_KEY in Vision/vlm/.env if you prefer

# terminal 1
make dev-merchant

# terminal 2
make dev-backend-host

# optional: seed the 9 demo bundles
make seed   # needs a running backend that can reach Postgres
# with host API: cd backend && .venv/bin/python seed.py
```

Open http://localhost:3000/merchant — upload a video or **Use demo sample**.
Leave **Expected items** blank for auto detection, or set `N` to trim to that count.

After processing completes, **Publish to catalogue**, then open the new listing
on the buyer dashboard and make an offer.

## Pre-demo checklist

1. `make nuke` — wipe containers **and** the DB volume (fresh start).
2. For buyer-only: `make dev` then `make seed`.
3. For merchant: `make setup-vision-envs`, then `make dev-merchant` +
   `make dev-backend-host`, then seed via host `python seed.py` if needed.
4. Confirm http://localhost:3000 shows cards; `/merchant` can run a sample.
5. Dry-run one full haggle including accept; confirm firm-price North Face.
6. If anything is off: `make logs` / host API terminal / `make logs-ui`.

## Demo script (buyer)

1. Dashboard → **Under Armour Sexy Shorts**.
2. **Make an offer** at a lowball — agent counters; floors stay hidden.
3. Haggle or **Accept seller's offer**.
4. Grade play on **Nike Vintage Tees Mix** — partial A/B selection.
5. Bonus: firm-price North Face; second browser profile as another buyer.

Full judge script: [`DEMO.md`](./DEMO.md).

## How the seller agent works

Per buyer turn (`backend/app/agent/`):

1. Build context from pluggable providers in `context.py` (listing, grades,
   haggle policy, negotiation state).
2. One structured LiteLLM call → `AgentDecision`.
3. Deterministic guardrails in `policy.py` (never below floor for the
   selected scope; stock caps; firm-price short-circuit).
4. Stream the final message as SSE tokens.

To add a context source, append a provider to `CONTEXT_PROVIDERS`.

Teammates also have `feat/agent-vision-signals` (not necessarily on `main`):
aggregates VLM defects / talking points into confidential `Item.vision_signals`
for photo-aware haggling. Merge that branch when you want vision in the agent.

## Item haggle metadata

Confidential (not on public `ItemRead`): `buying_price`,
`lowest_bundle_price` / `lowest_price_per_piece`, `grades[]`.

Public flags: `negotiable`, `high_quantity`.

Merchant publish fills demo constants (ask / floor / buying per piece) plus a
70/30 A/B grade split so make-offer works immediately after publish.

Tune seeded catalogue in `backend/seed.py`.

## Environment variables (root `.env`)

| Variable | Purpose |
| --- | --- |
| `LLM_MODEL` | LiteLLM model; unset → first available key (OpenRouter → Anthropic → OpenAI) |
| `LLM_FALLBACK_MODEL` | Optional second model on failure |
| `ANTHROPIC_API_KEY` | For `anthropic/...` |
| `OPENAI_API_KEY` | For `openai/...` |
| `OPENROUTER_API_KEY` | For `openrouter/...` (e.g. `openrouter/deepseek/deepseek-v4-flash`) |
| `GEMINI_API_KEY` | Merchant per-frame VLM (`Vision/vlm`) |
| `MERCHANT_SUMMARY_LLM` | Set `1` to try Gemini polish on the bundle summary (off by default) |
| `DATABASE_URL` | Host backend → Postgres (`postgresql+asyncpg://…@localhost:5432/app`) |
| `VITE_API_URL` | Set by `make dev-merchant` to `http://localhost:8000/api` |
| `BACKEND_URL` | Set by `make dev-merchant` to `http://host.docker.internal:8000` |

Without an LLM key the app still runs; the agent falls back to a canned reply.

## Make commands

| Command | What it does |
| --- | --- |
| `make dev` | Build + start ui, backend, Postgres |
| `make seed` | Load the 9 demo bundles (Docker backend) |
| `make nuke` | Stop everything and wipe the DB volume |
| `make down` | Stop containers (keep data) |
| `make migrate` | `alembic upgrade head` |
| `make makemigration m="..."` | Autogenerate a migration |
| `make logs` / `make logs-ui` | Tail backend / ui |
| `make lint` / `make format` | Ruff + ESLint / Ruff + Prettier |
| `make setup-vision-envs` | Create pySceneDetect + VLM virtualenvs |
| `make dev-merchant` | UI + Postgres for merchant (host API) |
| `make dev-backend-host` | FastAPI on host; stops Docker backend |

## Troubleshooting

- **Empty dashboard** — run `make seed` (or host `python seed.py`). Also check
  the API is actually up: `curl localhost:8000/api/items`. If the Docker
  backend crash-loops on `python-multipart`, rebuild: `docker compose build backend`.
- **Agent “lost my train of thought”** — LLM auth failed. Confirm root `.env`
  keys load on the **host** API (`LLM_MODEL` matches a non-empty key). Restart
  `make dev-backend-host` after editing `.env`.
- **Merchant: Missing extractor `/Vision/...`** — you are on the Docker
  backend. Switch to `make dev-backend-host`.
- **Port 8000 in use** — `docker compose stop backend` or
  `make dev-backend-host` (stops it for you).
- **No frames / Gemini errors** — `make setup-vision-envs`, set
  `GEMINI_API_KEY`, check `Vision/vlm/.env` for empty placeholders / zero-width
  characters in pasted keys.
- **Summary hung / timed out** — default path is local summary (no second
  Gemini). Do not enable `MERCHANT_SUMMARY_LLM` unless you need polish.
- **Published images 404 on buyer** — frames must be under
  `ui/public/merchant/{job_id}/` (publish copies them there).
- **Schema errors after pull** — `make nuke && make dev && make seed`.

## Layout

```
backend/
├── app/
│   ├── main.py              # FastAPI app, routers, /health
│   ├── config.py            # settings (loads backend/.env + repo .env)
│   ├── models.py            # items (+ image_urls), negotiations, messages
│   ├── schemas.py           # public schemas (no seller secrets)
│   ├── llm.py               # LiteLLM complete / structured / stream
│   ├── agent/               # seller: context, policy, negotiator, prompts
│   ├── merchant/            # jobs, pipeline, summarize, publish, paths, env
│   └── routers/             # items, negotiations, merchant (+ SSE)
├── alembic/                 # e.g. 0002_add_image_urls
├── data/merchant_jobs/      # local job workspace (gitignored)
└── seed.py
ui/
└── src/
    ├── routes/              # index, items.$itemId (gallery), merchant
    ├── components/merchant/ # upload, status, garment cards, summary
    └── lib/                 # api, merchant-api, types
Vision/
├── pySceneDetect/           # extract.py + .venv
├── vlm/                     # describe_crops.py + .venv
└── sample_video/            # demo haul clips
```

## Related docs

- [`DEMO.md`](./DEMO.md) — live demo script for judges
- [`backend/app/agent/`](./backend/app/agent/) — seller agent modules
- [`Vision/vlm/README.md`](./Vision/vlm/README.md) — Gemini / Qwen VLM setup
- [`Vision/pySceneDetect/README.md`](./Vision/pySceneDetect/README.md) — frame extractor
