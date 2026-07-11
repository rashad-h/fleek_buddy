---
name: llm
description: Call LLMs provider-agnostically via LiteLLM for completion, streaming, fallbacks, and JSON output in this FastAPI template.
---

# LLM Calls with LiteLLM

Use when adding or changing any LLM feature (chat, summarization, extraction, classification, agents). This template is **provider-agnostic via LiteLLM**: model strings are `provider/model`, keys are read from the environment, and swapping providers is a `.env` edit — no code change.

All LLM logic lives in `app/llm.py`; endpoints live in `app/routers/chat.py`. Add new LLM helpers to `app/llm.py` rather than calling `litellm` from routers.

## Config (`app/config.py`)

```python
llm_model: str = "anthropic/claude-sonnet-5"   # provider/model
llm_fallback_model: str | None = None          # optional second model
anthropic_api_key: str | None = None
openai_api_key: str | None = None
```

Valid model strings: `anthropic/claude-sonnet-5`, `anthropic/claude-opus-4-8`, `openai/gpt-5.1`.
Swap providers by editing `.env` only:

```dotenv
LLM_MODEL=openai/gpt-5.1
LLM_FALLBACK_MODEL=anthropic/claude-sonnet-5
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

`app/llm.py` mirrors `*_api_key` settings into `os.environ` so LiteLLM (which reads keys from the process env) picks them up whether they come from `.env` or the shell.

## Non-streaming completion

`litellm.acompletion` is the async entrypoint; the message content is at `response.choices[0].message.content`.

```python
response = await litellm.acompletion(model=model, messages=messages)
text = response.choices[0].message.content or ""
```

`messages` is a list of `{"role": ..., "content": ...}` dicts (OpenAI shape). In the router these come from `ChatRequest.messages` via `[m.model_dump() for m in request.messages]`.

## Streaming

Pass `stream=True`, then `async for chunk in response` and read `chunk.choices[0].delta.content` (may be `None` on some chunks — guard it):

```python
async def stream(messages: list[dict]) -> AsyncIterator[str]:
    response = await litellm.acompletion(
        model=settings.llm_model, messages=messages, stream=True
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
```

Wrap the async generator in a `StreamingResponse` in the router (see `app/routers/chat.py`):

```python
@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    messages = [m.model_dump() for m in request.messages]
    return StreamingResponse(llm.stream(messages), media_type="text/plain")
```

## Template fallback loop

`app/llm.py` tries `settings.llm_model`, then `settings.llm_fallback_model` if set, returning the first success and raising only if all fail:

```python
def _models() -> list[str]:
    models = [settings.llm_model]
    if settings.llm_fallback_model:
        models.append(settings.llm_fallback_model)
    return models

async def complete(messages: list[dict]) -> str:
    last_error: Exception | None = None
    for model in _models():
        try:
            response = await litellm.acompletion(model=model, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"All LLM providers failed: {last_error}")
```

This is intentionally minimal (good for a hackathon). For richer needs, LiteLLM has native features below.

## Native LiteLLM features worth knowing

**Per-call retries** — LiteLLM retries transient failures itself (exponential backoff on rate limits):

```python
response = await litellm.acompletion(model=model, messages=messages, num_retries=2)
```

**JSON / structured output** via `response_format`. Pass a Pydantic model (simplest) or a JSON schema; the content comes back as a JSON string to parse/validate:

```python
from pydantic import BaseModel

class Extract(BaseModel):
    name: str
    sentiment: str

response = await litellm.acompletion(
    model=settings.llm_model, messages=messages, response_format=Extract
)
result = Extract.model_validate_json(response.choices[0].message.content)
```

Or with an explicit schema: `response_format={"type": "json_schema", "json_schema": {"name": ..., "schema": {...}, "strict": True}}`.

**Router / fallbacks** — for load balancing across deployments or model-group fallbacks beyond the simple loop above, use `litellm.Router`:

```python
from litellm import Router

router = Router(
    model_list=[
        {"model_name": "primary",  "litellm_params": {"model": "anthropic/claude-sonnet-5"}},
        {"model_name": "backup",   "litellm_params": {"model": "openai/gpt-5.1"}},
    ],
    fallbacks=[{"primary": ["backup"]}],
    num_retries=2,
)
response = await router.acompletion(model="primary", messages=messages)
```

Prefer the template's `complete`/`stream` helpers for hackathon speed; reach for `Router` only when you need real load balancing or multi-deployment fallbacks.
