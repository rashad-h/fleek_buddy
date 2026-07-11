---
name: endpoints
description: Add or modify FastAPI API endpoints — routers, path/query/body params, Pydantic request/response models, status codes, and HTTPException in this template.
---

# Adding API Endpoints

Use when adding a new HTTP route or a whole new resource to this FastAPI (async, Pydantic v2) template.

## Where things live

- Routes group into an `APIRouter` per resource in `app/routers/` (see `app/routers/items.py`).
- Pydantic request/response models go in `app/schemas.py`.
- SQLAlchemy models go in `app/models.py`.
- Every router must be included in `app/main.py`.

## Steps

1. Add request/response schemas to `app/schemas.py` (Pydantic v2 `BaseModel`).
2. Create or extend a router in `app/routers/` with a `prefix` and `tags`.
3. Write async path operations; inject the DB session with `Depends(get_session)`.
4. Register the router in `app/main.py` via `app.include_router(...)`.

## Router setup

Create one `APIRouter` per resource. `prefix` is prepended to every path; `tags` groups them in the OpenAPI docs.

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import Item
from app.schemas import ItemCreate, ItemRead

router = APIRouter(prefix="/items", tags=["items"])
```

Include it in `app/main.py`:

```python
from app.routers import items

app.include_router(items.router)
```

## Request/response models

Define schemas in `app/schemas.py`. Use separate models for input and output. Read models that come from ORM objects set `from_attributes=True` so FastAPI can serialize the SQLAlchemy row.

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):
    title: str
    description: str | None = None


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    completed: bool
    created_at: datetime
```

`response_model=` validates and filters the response to the declared shape (e.g. it drops any extra fields). Use `response_model=list[ItemRead]` for collections.

## Body, path, and query params

A parameter typed as a Pydantic model is read from the JSON body; a name matching the path template (`{item_id}`) is a path param; anything else is a query param. Prefer `Annotated[..., Query(...)]` for query validation.

```python
from typing import Annotated


@router.get("", response_model=list[ItemRead])
async def list_items(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Item).order_by(Item.created_at.desc()).limit(limit)
    )
    return result.scalars().all()


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

## Status codes and errors

- Set a non-200 success code with `status_code=` on the decorator: `201` for create, `204` for delete (return `None`, no body).
- Raise `HTTPException(status_code=..., detail=...)` to short-circuit with an error response.

```python
@router.post("", response_model=ItemRead, status_code=201)
async def create_item(data: ItemCreate, session: AsyncSession = Depends(get_session)):
    item = Item(**data.model_dump())
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_item(item_id: int, session: AsyncSession = Depends(get_session)):
    item = await session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await session.delete(item)
    await session.commit()
```

## Conventions

- Path operations are `async def`.
- Router paths inside a prefixed router use `""` for the collection root (not `"/"`), matching `app/routers/items.py`.
- Commit then `await session.refresh(obj)` before returning so server-generated fields (`id`, `created_at`) are populated.
