# CLAUDE.md — FastAPI Template

Async Python API: FastAPI + SQLAlchemy 2.0 (async) + Postgres, Alembic,
Pydantic v2, and LiteLLM for a provider-agnostic LLM endpoint.

## Conventions (important)

- **Everything is async.** Endpoints are `async def`; the DB session is the
  async `get_session` dependency (`Depends(get_session)`).
- **SQLAlchemy 2.0** typed models: `DeclarativeBase` + `Mapped` / `mapped_column`.
  Query with `select(...)` + `await session.execute(...)` + `.scalars()`.
- **Pydantic v2**: response models use `ConfigDict(from_attributes=True)`; build
  ORM objects with `Model(**schema.model_dump())`.
- `DATABASE_URL` **must** use the async driver: `postgresql+asyncpg://…`.
- Python 3.12, 4-space indent, **Ruff** for lint/format.

## How to add X → see `.claude/skills/`

`endpoints`, `dependencies`, `database`, `migrations`, `validation-settings`,
`errors-middleware`, `llm`, `background-async`. These auto-activate; consult them
before hand-rolling patterns.

## Migrations (Alembic, async)

- Container runs `alembic upgrade head` on start, so `docker compose up` is enough.
- Change a model → `make makemigration m="add x"` → review the file in
  `alembic/versions/` → `make migrate`.
- `alembic/env.py` pulls the URL from `app.config.settings` and uses
  `Base.metadata` as `target_metadata`.

## LLM (LiteLLM)

- Model format is `provider/model` (e.g. `anthropic/claude-sonnet-5`,
  `openai/gpt-5.1`), read from `settings.llm_model`; optional `llm_fallback_model`.
- `app/llm.py` exposes `complete()` and `stream()`; `/chat/stream` wraps the
  generator in a `StreamingResponse`.
- LiteLLM reads provider keys from `os.environ`; `llm.py` mirrors any keys loaded
  from `.env` into the environment so both paths work.

## Env vars

`LLM_MODEL`, `LLM_FALLBACK_MODEL`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
`DATABASE_URL`. Copy `.env.example` → `.env`. In Docker, `DATABASE_URL` targets
the `db` service.

## Commands

`make dev | migrate | makemigration | seed | lint | format | down`.

## Comments

Keep them sparse — only where intent isn't obvious from the code.


## git
- Use conventinal commits
- When pushing, only run `git push`
- When creating a commit, only add a commit message, no description
- Do not mention you co-authored the PR

## Tone for any commented code
- Be clear but concise. Use plain language
- Prefer short but meaningful sentences over the use of hyphen/double hyphen, unless it reaaly fits a sentence

## Comments
- Only comment where anything really needs explenation, is unclear or has dependencies that the reader should be aware of
- Never use separators as comments, e.g. long sequence of `-` with some text

## Documentation
- Includes:
	- Class descriptions
	- Function documentation
	- Method documentation
	- Module/package documentation
	- Examples
- Only include what a reader should now
- Focus on the purpose and usage of a code element

## Python
- When possible add typing
- Never use `any` for typing
- Prefer a `TypeDict` with info on the return object over `dict` as type hint

## Typescript
- Never use `Any`/`any` for typing
