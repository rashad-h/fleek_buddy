import json
import os
import re
from collections.abc import AsyncIterator

import litellm
from pydantic import BaseModel

from app.config import settings

# LiteLLM reads provider keys from the process environment. Mirror any keys
# loaded from `.env` (via settings) into os.environ so both paths work.
for _field in ("anthropic_api_key", "openai_api_key"):
    _value = getattr(settings, _field)
    if _value:
        os.environ.setdefault(_field.upper(), _value)


def _models() -> list[str]:
    models = [settings.llm_model]
    if settings.llm_fallback_model:
        models.append(settings.llm_fallback_model)
    return models


async def complete(messages: list[dict]) -> str:
    """Non-streaming completion with a simple fallback to the next model."""
    last_error: Exception | None = None
    for model in _models():
        try:
            response = await litellm.acompletion(model=model, messages=messages)
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001 - fall through to the fallback model
            last_error = exc
    raise RuntimeError(f"All LLM providers failed: {last_error}")


async def complete_structured[T: BaseModel](messages: list[dict], schema: type[T]) -> T:
    """Completion parsed into `schema`, with a model fallback like `complete`.

    LiteLLM translates `response_format=<pydantic model>` per provider (for
    Anthropic it becomes a forced tool call). Some providers still wrap the
    JSON in prose, so parsing falls back to the first {...} block found.
    """
    last_error: Exception | None = None
    for model in _models():
        try:
            response = await litellm.acompletion(
                model=model, messages=messages, response_format=schema
            )
            content = response.choices[0].message.content or ""
            return _parse_structured(content, schema)
        except Exception as exc:  # noqa: BLE001 - fall through to the fallback model
            last_error = exc
    raise RuntimeError(f"All LLM providers failed: {last_error}")


def _parse_structured[T: BaseModel](content: str, schema: type[T]) -> T:
    try:
        return schema.model_validate_json(content)
    except ValueError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match is None:
            raise
        return schema.model_validate(json.loads(match.group()))


async def stream(messages: list[dict]) -> AsyncIterator[str]:
    """Yield response text chunks as they arrive."""
    response = await litellm.acompletion(model=settings.llm_model, messages=messages, stream=True)
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
