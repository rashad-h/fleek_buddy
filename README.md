# Fleek Buddy

Stack:
- **FastAPI** (async) + Uvicorn
- **SQLAlchemy 2.0 (async)** + asyncpg + Postgres, **Alembic** migrations
- **Pydantic v2** + pydantic-settings
- **LiteLLM** for a provider-agnostic LLM endpoint (Anthropic / OpenAI / 100+)
- Fully Dockerized (migrations auto-run on start); **Ruff**

## Quickstart

```bash
cp .env.example .env          # then add ANTHROPIC_API_KEY (needed only for /chat)
make dev                      # API → http://localhost:8000 (Swagger at /docs)
make seed                     # optional: load demo rows (in a second terminal)
```

`docker compose up` applies migrations automatically before starting the server.
Try it:

```bash
curl localhost:8000/health
curl -X POST localhost:8000/items -H 'Content-Type: application/json' \
  -d '{"title":"Demo"}'
curl -N -X POST localhost:8000/chat/stream -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"hi"}]}'
```

## Swap the LLM provider

Edit `.env` — no code changes. LiteLLM model format is `provider/model`:

```bash
LLM_MODEL=anthropic/claude-sonnet-5   # or anthropic/claude-opus-4-8, openai/gpt-5.1
LLM_FALLBACK_MODEL=                   # optional second model to try on failure
```

## Make commands

| Command                       | What it does                              |
| ----------------------------- | ----------------------------------------- |
| `make dev`                    | Start API + Postgres (reload, auto-migrate) |
| `make migrate`                | `alembic upgrade head`                    |
| `make makemigration m="..."`  | Autogenerate a migration from the models  |
| `make seed`                   | Load demo data                            |
| `make lint` / `make format`   | Ruff check / format                       |
| `make down`                   | Stop containers                           |

## Layout

```
app/
├── main.py            # app factory, CORS, router include, /health
├── config.py          # pydantic-settings (env)
├── db.py              # async engine + session dependency
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic request/response models
├── routers/           # items (CRUD) + chat (/chat, /chat/stream)
└── llm.py             # LiteLLM wrapper (complete + stream, fallback)
alembic/               # async migrations
```

## Working with Claude Code

`.claude/skills/` ships doc-derived skills (endpoints, database, migrations,
dependencies, validation-settings, errors-middleware, llm, background-async)
that auto-activate. See `CLAUDE.md` for conventions.

## Deploy

The `prod` Docker target installs the package and runs Uvicorn as a non-root
user (after applying migrations).
