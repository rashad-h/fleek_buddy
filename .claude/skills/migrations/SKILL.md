---
name: migrations
description: Create, apply, and roll back Alembic (async) database migrations in this template when changing SQLAlchemy models, running upgrade/downgrade, or autogenerating revisions.
---

# Alembic Migrations (async)

Use this whenever a SQLAlchemy model changes (new table/column, type or
constraint change) and Postgres needs to match. Alembic here runs against the
same async `postgresql+asyncpg://` engine as the app, driven through
`connection.run_sync`. Day-to-day you'll use the `make` targets below.

## Everyday commands (`Makefile`)

Migrations run inside the running `app` container via docker compose:

```bash
make makemigration m="add items table"   # autogenerate a revision from model diffs
make migrate                             # apply: alembic upgrade head
```

Under the hood these are:
- `make makemigration` -> `alembic revision --autogenerate -m "$(m)"`
- `make migrate`       -> `alembic upgrade head`

Autogenerate diffs `Base.metadata` (all models under `app.models.Base`) against
the live database and writes a new file in `alembic/versions/`. **Always open
and review the generated script** — autogenerate can miss server defaults, type
changes, and renames; edit before applying.

To roll back one step (run in the container, e.g. `docker compose exec app ...`):

```bash
alembic downgrade -1      # undo the most recent revision
alembic downgrade base    # undo everything
```

## Auto-apply on container start

You rarely run `make migrate` by hand at boot: both Docker targets run
`alembic upgrade head` before launching uvicorn (`Dockerfile` CMD), so a fresh
`make dev` brings the schema up to date automatically once Postgres is healthy
(`docker-compose.yml` waits on the `db` healthcheck). Use `make migrate`
explicitly only when applying a migration to an already-running stack.

## Async `env.py` setup (`alembic/env.py`)

Key wiring — do not revert these to the sync defaults:

```python
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.models import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)  # URL from settings, not alembic.ini

target_metadata = Base.metadata  # what --autogenerate compares against


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)  # sync migration API over an async connection
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())
```

Why it looks like this:
- The DB URL comes from `app.config.settings.database_url`, so `alembic.ini` has
  no hardcoded URL (`sqlalchemy.url` is set at runtime).
- `target_metadata = Base.metadata` — any model must be imported/reachable from
  `app.models` for autogenerate to detect it.
- Alembic's migration operations are synchronous, so `run_async_migrations`
  opens an async connection and runs them via `connection.run_sync`.
- `NullPool` avoids leaving pooled connections open across the short-lived
  migration process.

## Revision file shape (`alembic/versions/0001_init.py`)

Each revision has string `revision` / `down_revision` identifiers and
`upgrade()` / `downgrade()` using `op` + `sa`:

```python
import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None  # first migration; later files point at the previous revision id


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("items")
```

Always fill in a real `downgrade()` so `alembic downgrade` works — autogenerate
produces one, but verify it reverses the upgrade.

## Typical workflow

1. Edit a model in `app/models.py` (see the `database` skill).
2. `make makemigration m="describe the change"`.
3. Review the new file in `alembic/versions/` (defaults, nullability, renames).
4. `make migrate` to apply (or just restart the stack — it upgrades on boot).
