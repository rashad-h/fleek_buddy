---
name: dependencies
description: Use FastAPI dependency injection — Depends, the async DB session (get_session), settings, sub-dependencies, and API-key/header auth dependencies in this template.
---

# Dependency Injection

Use when injecting shared logic into path operations: the DB session, settings, auth checks, or reusable parameter parsing. This template is async FastAPI with Pydantic v2 and async SQLAlchemy.

## The DB session dependency

`app/db.py` exposes `get_session`, a yield-generator that opens an `AsyncSession` per request and closes it on the way out. Inject it into any path operation.

```python
# app/db.py
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
```

Inject with `Depends` (matches `app/routers/items.py`):

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session


@router.get("")
async def list_items(session: AsyncSession = Depends(get_session)):
    ...
```

The code before `yield` runs before the request; the `async with` block's exit runs after the response is sent — so the session is always closed even on error.

## Settings injection

`app/config.py` builds a single `settings` instance (Pydantic Settings, values from env / `.env`). Import it directly for module-level use (as `app/db.py` does):

```python
from app.config import settings

model = settings.llm_model
```

To make settings overridable in tests, wrap it in a dependency instead:

```python
from functools import lru_cache

from app.config import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()


@router.get("/config")
async def read_config(settings: Settings = Depends(get_settings)):
    return {"model": settings.llm_model}
```

Override in tests via `app.dependency_overrides[get_settings] = lambda: Settings(...)`.

## Reusable dependencies with Annotated

Factor shared params into a function and alias it to cut repetition. The alias is reused across path operations:

```python
from typing import Annotated

from fastapi import Depends


async def pagination(skip: int = 0, limit: int = 100) -> dict:
    return {"skip": skip, "limit": limit}


Pagination = Annotated[dict, Depends(pagination)]


@router.get("")
async def list_items(page: Pagination):
    return page
```

## Sub-dependencies

A dependency may itself declare dependencies; FastAPI resolves the whole chain and caches each dependency per request.

```python
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Item


async def get_item_or_404(
    item_id: int, session: Annotated[AsyncSession, Depends(get_session)]
) -> Item:
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item: Annotated[Item, Depends(get_item_or_404)]):
    return item  # get_session was resolved once and reused
```

## API-key auth dependency

Read a header and reject unauthorized requests. Use `Header` for a plain check, or `APIKeyHeader` (from `fastapi.security`) so the key shows in the OpenAPI docs.

```python
from typing import Annotated

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(key: Annotated[str, Security(api_key_header)]) -> None:
    if key != settings.api_key:  # add `api_key` to Settings in app/config.py
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key"
        )
```

Apply it per-route:

```python
@router.post("", dependencies=[Depends(require_api_key)])
async def create_item(...):
    ...
```

Apply it to a whole router or the whole app:

```python
router = APIRouter(prefix="/items", tags=["items"], dependencies=[Depends(require_api_key)])
# or in app/main.py:
app.include_router(items.router, dependencies=[Depends(require_api_key)])
```

Dependencies used only for their side effect (auth) return `None` and belong in the `dependencies=[...]` list rather than a function parameter.

## Conventions

- Dependencies are `async def`; inject with `Depends(...)` (or `Security(...)` for scheme-aware auth).
- Prefer `Annotated[Type, Depends(...)]` for reusable/typed dependencies.
- Never construct `AsyncSession` manually in routes — always `Depends(get_session)`.
