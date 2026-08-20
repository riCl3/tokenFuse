"""Streaming (SSE) test: the proxy forwards all chunks including [DONE], and
the background tap records usage (Postgres row + Redis window)."""

import httpx
import respx
from sqlalchemy import select

from app.core.redis_client import redis
from app.db.models import UsageEvent
from app.services import budget_service

PROVIDER_URL = "http://provider.test/v1/chat/completions"


@respx.mock
async def test_streaming_forwards_and_records(client, create_project, db):
    project_id, key = await create_project(monthly=70.0)

    async def events():
        yield b'data: {"id":"1","object":"chat.completion.chunk","model":"gpt-4o","choices":[{"index":0,"delta":{"content":"Hello "},"finish_reason":null}]}\n\n'
        yield b'data: {"id":"1","object":"chat.completion.chunk","model":"gpt-4o","choices":[{"index":0,"delta":{"content":"world"},"finish_reason":null}]}\n\n'
        yield b'data: {"id":"1","object":"chat.completion.chunk","model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}\n\n'
        yield b'data: {"id":"1","object":"chat.completion.chunk","model":"gpt-4o","choices":[],"usage":{"prompt_tokens":5000,"completion_tokens":3000,"total_tokens":8000}}\n\n'
        yield b"data: [DONE]\n\n"

    respx.post(PROVIDER_URL).mock(
        return_value=httpx.Response(
            200,
            stream=events(),
            headers={"content-type": "text/event-stream"},
        )
    )

    resp = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": True,
        },
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert '"content":"Hello "' in resp.text
    assert '"content":"world"' in resp.text
    assert '"usage"' in resp.text
    assert "data: [DONE]" in resp.text

    # On a normal completion the generator awaits the tap before finishing, so
    # the usage row and Redis event already exist once the response is read.
    event = (
        await db.execute(select(UsageEvent).where(UsageEvent.project_id == project_id))
    ).scalar_one()
    assert event.streamed is True
    assert event.total_tokens == 8000
    assert float(event.cost_usd) == 0.0425

    members = await redis.zrange(budget_service.window_key(project_id), 0, -1)
    assert len(members) == 1