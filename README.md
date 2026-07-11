# Fleek Buddy

A Fleek-style wholesale marketplace demo where **you are the buyer** and every
listing is defended by an **LLM seller agent** that haggles with you in a
real-time chat: it counters, holds firm, accepts or walks away based on each
item's confidential haggle metadata.

## Architecture

```
browser :3000 ──> ui (TanStack Start, Vite dev server)
                    └── /api proxy ──> backend :8000 (FastAPI)
                                          ├── Postgres :5432 (items, negotiations, messages)
                                          └── LiteLLM ──> Anthropic / OpenAI (seller agent)
```

- `ui/` — presentation only. TanStack Start + Query, Tailwind v4, shadcn/ui.
  All data comes from the backend through the Vite `/api` proxy (no CORS, no
  keys in the browser).
- `backend/` — FastAPI + async SQLAlchemy. The seller agent lives in
  `backend/app/agent/`: one structured LLM call per turn, deterministic
  guardrails on top (never sells below the floor), reply streamed as SSE.

## Quickstart

Requires Docker. One command runs everything:

```bash
cp .env.example .env          # add your ANTHROPIC_API_KEY (the agent needs it)
make dev                      # ui → http://localhost:3000, api → :8000/docs
make seed                     # in a second terminal: load the 9 demo bundles
```

Migrations apply automatically when the backend container starts.

## Pre-demo checklist

Do this ~10 minutes before demoing:

1. `make nuke` — wipe containers **and** the database volume (fresh start).
2. `make dev` — wait until the ui, backend and db services are all up
   (backend logs end with `Application startup complete`).
3. `make seed` — should print `Seeded 9 bundles.`
4. Open http://localhost:3000 — verify all 9 product cards render with
   images, per-piece prices and discount badges.
5. Dry-run one full haggle (see demo script below) **including an accept**,
   then reload the page — the item should show the deal as agreed.
6. Open "The North Face Fleeces" and lowball it — the agent must hold firm
   (this item is seeded `negotiable=false`).
7. If anything is off: `make logs` / `make logs-ui`.

## Demo script

1. Dashboard → open **Under Armour Sexy Shorts** (£171.35 bundle, £4.35/pc).
2. Click **Make an offer**, offer **£90** — the chat drawer opens and the
   agent counters in real time (it will never go below its hidden floor).
3. Haggle in the chat; send **£140** as a new offer ("Offer £" field).
4. The agent accepts around there → gold "transaction complete" banner, chat
   locks.
5. Bonus: show the North Face item refusing to budge, or open a second
   browser profile to run a parallel negotiation as another buyer.

## How the seller agent works

Per buyer turn, the backend builds a context from pluggable providers
(`backend/app/agent/context.py`): listing facts, the confidential haggle
policy (cost, floor price, `negotiable`, `high_quantity` flags), and the
negotiation state. One LiteLLM call returns a structured decision
(`counter | accept | reject | chat` + price + message); code-level guardrails
(`policy.py`) then clamp it — accepts below the floor become counters,
counters can only move downwards, non-negotiable items short-circuit the LLM
entirely. The final message streams to the browser as SSE tokens.

To enrich the agent with a new context source, add one function to
`CONTEXT_PROVIDERS` in `context.py`.

## Item haggle metadata

Each seeded item carries (never exposed via the API): `buying_price` (what
the seller paid), `lowest_bundle_price` / `lowest_price_per_piece` (hard
floor), plus public flags `negotiable` and `high_quantity` (high stock makes
the agent concede faster). Tune them in `backend/seed.py`.

## Environment variables (root `.env`)

| Variable             | Purpose                                             |
| -------------------- | --------------------------------------------------- |
| `ANTHROPIC_API_KEY`  | Seller agent LLM (required for real negotiations)   |
| `LLM_MODEL`          | LiteLLM model, default `anthropic/claude-sonnet-5`  |
| `LLM_FALLBACK_MODEL` | Optional second model tried on failure              |
| `OPENAI_API_KEY`     | Only if you switch `LLM_MODEL` to an OpenAI model   |
| `DATABASE_URL`       | Only for running the backend outside Docker         |

Without an API key the app still runs: the agent answers with a safe canned
reply (and non-negotiable items always work), but real haggling needs a key.

## Make commands

| Command                      | What it does                                   |
| ---------------------------- | ---------------------------------------------- |
| `make dev`                   | Build + start ui, backend and Postgres         |
| `make seed`                  | Load the demo catalogue (idempotent)           |
| `make nuke`                  | Stop everything and wipe the DB volume         |
| `make down`                  | Stop containers (keep data)                    |
| `make migrate`               | `alembic upgrade head` in the backend          |
| `make makemigration m="..."` | Autogenerate a migration                       |
| `make logs` / `make logs-ui` | Tail backend / ui logs                         |
| `make lint` / `make format`  | Ruff + ESLint / Ruff + Prettier                |

## Troubleshooting

- **Cards don't load / empty dashboard** — did you run `make seed`? Check
  `curl localhost:8000/api/items`.
- **Schema errors after pulling changes** — the demo replaces migrations
  in-place; run `make nuke && make dev && make seed`.
- **Agent replies "lost my train of thought"** — the LLM call failed; check
  `ANTHROPIC_API_KEY` in `.env` and `make logs`.
- **Chat doesn't stream** — the Vite proxy should pass SSE through; as a
  fallback set `VITE_API_URL=http://localhost:8000/api` for the ui service
  (backend CORS already allows it) and restart.
- **Port clashes** — 3000, 8000 and 5432 must be free.

## Layout

```
backend/
├── app/
│   ├── main.py            # FastAPI app, /api routers, /health
│   ├── models.py          # items, negotiations, messages
│   ├── schemas.py         # public read/write schemas (no seller secrets)
│   ├── llm.py             # LiteLLM wrapper + structured output
│   ├── agent/             # seller agent: context, policy, negotiator, prompts
│   └── routers/           # items (read-only), negotiations (+ SSE)
├── alembic/               # migrations (auto-applied on start)
└── seed.py                # demo catalogue
ui/
└── src/
    ├── routes/            # index (dashboard), items.$itemId (detail)
    ├── components/        # ProductCard, OfferModal, NegotiationDrawer
    └── lib/               # api client + SSE parser, types, buyer id
```
