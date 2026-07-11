---
name: errors-middleware
description: Raise HTTPException, register custom exception handlers with JSONResponse, override validation errors, and add CORS or custom http middleware in FastAPI.
---

# Errors & Middleware (FastAPI)

Use this when a route needs to signal an error status, when you want app-wide handling for an exception or invalid request bodies, or when adding cross-cutting request/response logic.

## Raising errors in routes (`app/routers/items.py`)

Raise `HTTPException` with a status code and detail. FastAPI turns it into a JSON `{"detail": ...}` response.

```python
from fastapi import HTTPException

item = await session.get(Item, item_id)
if item is None:
    raise HTTPException(status_code=404, detail="Item not found")
```

- Add headers with `HTTPException(status_code=401, detail="...", headers={"WWW-Authenticate": "Bearer"})`.
- Prefer `HTTPException` for expected client errors; let unexpected errors bubble to a custom handler (below).

## Custom exception handlers

Register app-wide handlers in `app/main.py` with `@app.exception_handler(...)`. The handler receives the `Request` and the exception and returns a `JSONResponse`.

```python
from fastapi import Request
from fastapi.responses import JSONResponse


class ItemUnavailable(Exception):
    def __init__(self, item_id: int):
        self.item_id = item_id


@app.exception_handler(ItemUnavailable)
async def item_unavailable_handler(request: Request, exc: ItemUnavailable) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={"message": f"Item {exc.item_id} is unavailable"},
    )
```

Now any route can `raise ItemUnavailable(item_id)` and get a consistent 409.

## Overriding request-validation errors

FastAPI raises `RequestValidationError` (422) for invalid request data. Override its handler to shape the response:

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},   # add exc.body to echo the bad payload
    )
```

- `exc.errors()` is the list of per-field errors; `exc.body` is the raw request body.
- You can likewise override the built-in `HTTPException` handler with `@app.exception_handler(HTTPException)`.

## Middleware

### CORS (already configured in `app/main.py`)

```python
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Origins come from settings. Add `allow_credentials=True` if the frontend sends cookies/auth — but then `allow_origins` cannot be `["*"]`; list explicit origins.

### Custom http middleware

For cross-cutting logic (timing, request IDs, auth prep), use `@app.middleware("http")`. Call `call_next(request)` to run the route, then modify the response before returning it.

```python
import time

from fastapi import Request


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Process-Time"] = str(time.perf_counter() - start)
    return response
```

- The middleware function is `async` and must return the `call_next` response.
- With `add_middleware`, the last-added middleware is outermost (runs first on the request, last on the response).
