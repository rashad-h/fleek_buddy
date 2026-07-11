---
name: validation-settings
description: Define Pydantic v2 request/response models and pydantic-settings config when adding endpoints, serializing ORM rows, or reading env vars.
---

# Validation & Settings (Pydantic v2 + pydantic-settings)

Use this when adding a new endpoint's request/response shapes, serializing SQLAlchemy rows to JSON, or wiring a new config value from the environment.

## Request / response models (`app/schemas.py`)

Each endpoint gets explicit models. Inputs use plain `BaseModel`; the read/response model adds `ConfigDict(from_attributes=True)` so FastAPI can serialize an ORM instance directly.

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):          # request body
    title: str
    description: str | None = None


class ItemRead(BaseModel):            # response, built from an ORM row
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    completed: bool
    created_at: datetime
```

- `from_attributes=True` lets Pydantic read attributes off arbitrary objects (SQLAlchemy models), not just dicts. Without it, returning an ORM instance for a `response_model` fails.
- Use `str | None = None` for optional fields; a bare `str | None` (no default) is required-but-nullable.

## Serializing to/from ORM

In routers, `response_model=ItemRead` tells FastAPI to validate the returned ORM row through the model automatically:

```python
@router.get("", response_model=list[ItemRead])
async def list_items(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Item).order_by(Item.created_at.desc()))
    return result.scalars().all()   # ORM rows -> ItemRead via from_attributes
```

To build an ORM object from a request model, dump it to a dict:

```python
item = Item(**data.model_dump())    # data: ItemCreate
```

- `model_dump()` returns a plain dict; add `model_dump(exclude_unset=True)` for partial updates (PATCH), so unset fields don't overwrite existing values.
- To validate an ORM instance explicitly outside a route: `ItemRead.model_validate(orm_obj)`.

## Settings (`app/config.py`)

`Settings` subclasses `BaseSettings`. Fields are typed; values come from the environment or `.env`, and env matching is case-insensitive by default.

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_model: str = "anthropic/claude-sonnet-5"
    anthropic_api_key: str | None = None
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app"
    cors_origins: list[str] = ["*"]


settings = Settings()   # instantiated once; import `settings` elsewhere
```

- A field `database_url` is populated from env var `DATABASE_URL` / `database_url` (case-insensitive) or the `.env` line `DATABASE_URL=...`; otherwise the default is used.
- `extra="ignore"` drops unknown env keys instead of erroring — keep it so an unrelated `.env` entry doesn't crash startup.
- Fields without a default (e.g. `api_key: str`) are required and raise a `ValidationError` at startup if missing.
- `list[str]` fields accept JSON in the env (`CORS_ORIGINS=["http://localhost:3000"]`).

Add a new setting by declaring a typed field with a default; import via `from app.config import settings` and read `settings.<field>`.
