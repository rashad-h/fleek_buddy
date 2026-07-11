import os
from collections.abc import AsyncIterator

import litellm

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


async def stream(messages: list[dict]) -> AsyncIterator[str]:
    """Yield response text chunks as they arrive."""
    response = await litellm.acompletion(
        model=settings.llm_model, messages=messages, stream=True
    )
    async for chunk in response:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
