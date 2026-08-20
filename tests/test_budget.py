"""Budget + proxy tests: budget-exceeded -> 429, successful completion records
usage (Postgres row + Redis window). Provider calls are mocked with RespX."""

import httpx
import respx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.redis_client import redis
from app.db.models import UsageEvent
from app.services import budget_service

settings = get_settings()

PROVIDER_URL = "http://provider.test/v1/chat/completions"


async def _seed_spend(project_id: int, count: int, cost: float = 0.0425) -> None:
    for _ in range(count):
        await budget_service.record_usage(project_id, cost)


@respx.mock
async def test_budget_exceeded_429(client, create_project):
    # monthly $70 -> hourly window budget = 97,222 units
    project_id, key = await create_project(monthly=70.0)
    await _seed_spend(project_id, 3)  # 3 x 42,500 = 127,500 units > 97,222

    route = respx.post(PROVIDER_URL).mock(return_value=httpx.Response(200, json={}))

    resp = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 429
    detail = resp.json()["detail"]
    assert detail["error"] == "budget_exceeded"
    assert detail["used_units"] == 127500
    assert detail["budget_units"] == 97222
    assert not route.called  # nothing forwarded upstream once budget is gone


@respx.mock
async def test_non_streaming_success_records_usage(client, create_project, db):
    project_id, key = await create_project(monthly=70.0)

    provider_payload = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hi"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5000, "completion_tokens": 3000, "total_tokens": 8000},
    }
    respx.post(PROVIDER_URL).mock(return_value=httpx.Response(200, json=provider_payload))

    resp = await client.post(
        "/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert resp.status_code == 200
    assert resp.json()["choices"][0]["message"]["content"] == "hi"

    event = (
        await db.execute(select(UsageEvent).where(UsageEvent.project_id == project_id))
    ).scalar_one()
    assert event.total_tokens == 8000
    assert float(event.cost_usd) == 0.0425
    assert event.streamed is False

    members = await redis.zrange(budget_service.window_key(project_id), 0, -1)
    assert len(members) == 1