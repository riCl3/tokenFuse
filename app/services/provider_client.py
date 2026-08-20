from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

settings = get_settings()

_PROVIDERS = {
    "openai": (settings.openai_base_url, settings.openai_api_key),
    "openrouter": (settings.openrouter_base_url, settings.openrouter_api_key),
}

client = httpx.AsyncClient(timeout=settings.provider_timeout_seconds)


@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class CompletionResult:
    data: dict
    usage: TokenUsage | None


async def forward_chat_completion(payload: dict, provider: str) -> CompletionResult:
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    base_url, api_key = _PROVIDERS[provider]

    response = await client.post(
        f"{base_url}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
    )
    response.raise_for_status()

    data = response.json()
    usage_raw = data.get("usage")
    usage = None
    if usage_raw:
        usage = TokenUsage(
            prompt_tokens=usage_raw.get("prompt_tokens", 0),
            completion_tokens=usage_raw.get("completion_tokens", 0),
            total_tokens=usage_raw.get("total_tokens", 0),
        )
    return CompletionResult(data=data, usage=usage)


async def stream_chat_completion(
    payload: dict, provider: str
) -> AsyncIterator[bytes]:
    """Forward a chat completion and yield the raw SSE bytes as they arrive.

    Unlike forward_chat_completion, nothing is buffered: each `yield` emits
    one upstream chunk (typically a single `data: {...}` SSE block). The caller
    forwards each chunk to the client immediately and can parse it on the side.
    """
    if provider not in _PROVIDERS:
        raise ValueError(f"Unknown provider: {provider}")
    base_url, api_key = _PROVIDERS[provider]

    async with client.stream(
        "POST",
        f"{base_url}/chat/completions",
        json=payload,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
    ) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes():
            yield chunk


async def close() -> None:
    await client.aclose()