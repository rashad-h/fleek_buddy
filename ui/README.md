# TanStack Start Template

A hackathon-ready **full-stack** starter, all-in on the TanStack ecosystem.

- **TanStack Start** (file-based routing, SSR, server functions) on Vite
- **TanStack Query / Form / Table** for data, forms, and tables
- **Drizzle ORM + Postgres**
- **Tailwind v4 + shadcn/ui**
- **TanStack AI** for a provider-agnostic streaming LLM chat (Anthropic / OpenAI / …)
- Fully Dockerized with hot reload; **ESLint + Prettier**

## When to pick this

You want one repo with UI **and** backend, type-safe end to end, and an LLM
chat wired in.

## Quickstart

```bash
cp .env.example .env          # then add ANTHROPIC_API_KEY (needed only for /chat)
make dev                      # app → http://localhost:3000, Postgres in Docker
```

In a second terminal (first run creates the tables):

```bash
make db-push                  # push the Drizzle schema to Postgres
make seed                     # optional: load demo rows
```

Open http://localhost:3000 — **/chat** streams from the LLM, **/items** is a
CRUD demo using Form + Table + Drizzle.

## Swap the LLM provider

Edit `.env` — no code changes:

```bash
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-5     # or claude-opus-4-8
# LLM_PROVIDER=openai
# LLM_MODEL=gpt-5.1
```

## Make commands

| Command          | What it does                         |
| ---------------- | ------------------------------------ |
| `make dev`       | Start app + Postgres with hot reload |
| `make db-push`   | Push the Drizzle schema to Postgres  |
| `make seed`      | Load demo data                       |
| `make lint`      | ESLint                               |
| `make format`    | Prettier + ESLint autofix            |
| `make typecheck` | `tsc --noEmit`                       |
| `make build`     | Build the production image           |
| `make down`      | Stop containers                      |

## Layout

```
src/
├── routes/            # file-based routes; api/chat.ts is the LLM endpoint
├── server/            # server functions (items.ts) + LLM adapter (llm.ts)
├── db/                # Drizzle schema + client
├── components/ui/     # shadcn/ui primitives
└── router.tsx         # router + TanStack Query wiring
```

## Working with Claude Code

`.claude/skills/` ships doc-derived skills (routing, server functions, data
fetching, forms, tables, database, UI, LLM) that auto-activate for common tasks.
See `CLAUDE.md` for conventions.

## Deploy

`make build` produces a self-contained Nitro server (`.output/server/index.mjs`,
run with `node`). The `prod` Docker target runs it as a non-root user.

> Note: TanStack Start is currently in **alpha** — expect occasional churn.
