---
name: background-async
description: Write async endpoints, run fire-and-forget BackgroundTasks, manage lifespan startup/shutdown, and offload blocking calls in this FastAPI template.
---

# Async & Background Work

Use when adding endpoints, running work after the response is sent, wiring startup/shutdown resources, or calling a blocking (sync) library from an async route. This template is async-first: routes are `async def` and the DB uses `AsyncSession` (see `app/routers/items.py`, `app/routers/chat.py`, `app/main.py`).

## `async def` vs `def`

- Use **`async def`** when the handler `await`s something (LLM calls via `app/llm.py`, DB via `AsyncSession`, `httpx`). This is the template default — every route in `app/routers/` and `app/main.py:health` is `async def`.
- Use plain **`def`** when the handler only calls a **blocking** (non-awaitable) library. FastAPI runs `def` handlers in a threadpool automatically, so they don't block the event loop.

```python
@app.get("/report")
def build_report():          # sync lib -> def, runs in threadpool
    return heavy_sync_lib()
```

Never call a blocking function directly inside an `async def` handler — it stalls the whole event loop.

## Blocking calls inside an async handler

If you must stay `async def` (e.g. you also `await` something) but need to call blocking code, offload it with `run_in_threadpool`:

```python
from fastapi.concurrency import run_in_threadpool

@router.post("/process")
async def process(data: Payload):
    result = await run_in_threadpool(blocking_cpu_bound, data)  # off the event loop
    saved = await save(result)                                   # real await
    return saved
```

## BackgroundTasks — fire-and-forget after responding

Declare a `BackgroundTasks` parameter and `add_task(fn, *args)`. The task runs **after** the response is sent, so the client isn't blocked. The task fn may be `def` or `async def`.

```python
from fastapi import APIRouter, BackgroundTasks

@router.post("/chat")
async def chat(request: ChatRequest, tasks: BackgroundTasks) -> dict[str, str]:
    messages = [m.model_dump() for m in request.messages]
    reply = await llm.complete(messages)
    tasks.add_task(log_conversation, messages, reply)  # runs after response returns
    return {"content": reply}
```

Good for: logging, sending notifications, cache warmup, cheap follow-up writes. Not for: long/critical jobs needing retries or durability (use a real queue). Tasks run in the same process, so a crash loses them. Dependency cleanup (e.g. DB sessions from `Depends`) happens *after* background tasks finish, so a task can still use dependency-provided state passed into it.

## Lifespan — startup / shutdown

Use a single `@asynccontextmanager` for resources that live for the app's lifetime (clients, pools, model warmup). Code before `yield` runs at startup; after `yield` at shutdown. Pass it as `lifespan=` to `FastAPI(...)`.

`app/main.py` currently constructs the app as `app = FastAPI(title="FastAPI Template")`. To add lifespan, wire it like this:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

resources: dict = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: open shared resources
    resources["http"] = make_http_client()
    yield
    # shutdown: clean up
    await resources["http"].aclose()
    resources.clear()

app = FastAPI(title="FastAPI Template", lifespan=lifespan)
```

`lifespan` supersedes the older `@app.on_event("startup"/"shutdown")` handlers — use `lifespan` for new code. Keep the existing middleware and `include_router` calls after the `app = FastAPI(...)` line as they are in `app/main.py`.
