---
name: database
description: Query and mutate Postgres with async SQLAlchemy 2.0 (asyncpg) when adding models, endpoints, sessions, or select/get/add/commit/delete logic in this template.
---

# Async SQLAlchemy 2.0 (asyncpg + Postgres)

Use this when defining ORM models, wiring the async engine/session, or writing
data-access code inside FastAPI endpoints. This template is **fully async**:
every DB call is awaited and the driver is `postgresql+asyncpg://`.

## Engine & session (`app/db.py`)

One engine + one `async_sessionmaker` for the whole app. `expire_on_commit=False`
is required so returned ORM objects stay usable after `commit()` (e.g. when
FastAPI serializes them) without triggering a lazy reload on an already-closed
async context.

```python
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

`get_session` is the FastAPI dependency; inject it as
`session: AsyncSession = Depends(get_session)`. The `async with` block closes the
session (and rolls back if uncommitted) when the request finishes.

## Models (`app/models.py`)

SQLAlchemy 2.0 declarative style: a single `Base(DeclarativeBase)` and
`Mapped[...]` annotations. The annotation drives the column type and nullability;
add `mapped_column(...)` only for extra config (primary key, defaults,
server defaults). `Base.metadata` is what Alembic autogenerate compares against.

```python
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str]                                        # NOT NULL
    description: Mapped[str | None] = mapped_column(default=None)  # str | None -> NULL
    completed: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

Rules of thumb:
- `Mapped[str]` -> NOT NULL; `Mapped[str | None]` -> nullable.
- `default=` is a Python-side default; `server_default=` emits it in the DDL
  (so it also applies to rows inserted outside the app).
- New models must live under `Base` so Alembic sees them — then generate a
  migration (see the `migrations` skill).

## Query patterns in endpoints (`app/routers/items.py`)

All calls are `await`ed against the injected `AsyncSession`.

**SELECT many** — build a statement with `select(...)`, `await session.execute`,
then `.scalars().all()` to get ORM instances instead of `Row` tuples:

```python
result = await session.execute(select(Item).order_by(Item.created_at.desc()))
items = result.scalars().all()
```

**INSERT** — construct, `add`, `commit`, then `refresh` to populate
server-generated columns (`id`, `created_at`):

```python
item = Item(**data.model_dump())
session.add(item)
await session.commit()
await session.refresh(item)
```

**Fetch by primary key** — `session.get` returns the instance or `None`:

```python
item = await session.get(Item, item_id)
if item is None:
    raise HTTPException(status_code=404, detail="Item not found")
```

**UPDATE** — mutate the loaded instance, then `commit` (+ `refresh` if you return it):

```python
item.completed = data.completed
await session.commit()
await session.refresh(item)
```

**DELETE** — `await session.delete(...)` then `commit`:

```python
await session.delete(item)
await session.commit()
```

Notes:
- `select`, `func`, etc. import from `sqlalchemy`; `AsyncSession` and the async
  engine/sessionmaker from `sqlalchemy.ext.asyncio`.
- `session.execute` and `session.get` are coroutines here — always `await`.
- After a schema change to a model, add a migration and apply it with
  `make migrate` before the new column/table exists in Postgres.
