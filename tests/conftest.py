"""Shared fixtures for the TokenFuse test suite.

Design notes:
- The DATABASE_URL / OPENAI_BASE_URL env vars are set BEFORE the app is
  imported, so every module that builds its session factory / provider client
  from settings automatically targets the TEST Postgres DB and a fake provider
  host. RespX intercepts all httpx traffic, so no real API is ever hit.
- Uses the real local Redis (Docker) for budget tests; keys created during a
  test are deleted afterwards by the autouse cleanup fixture.
- Postgres: a dedicated `tokenfuse_test` database must exist:
    docker exec tokenfuse-pg psql -U postgres -c "CREATE DATABASE tokenfuse_test;"
"""

import os

os.environ["DATABASE_URL"] = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/tokenfuse_test"
)
os.environ["OPENAI_BASE_URL"] = "http://provider.test/v1"

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.base as db_base
from app.core.redis_client import redis
from app.db.base import Base
from app.main import app

_created_project_ids: list[int] = []


@pytest.fixture(scope="session", autouse=True)
async def _tables():
    """Create the schema once for the session, drop it at the end."""
    async with db_base.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with db_base.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await db_base.engine.dispose()


@pytest.fixture(autouse=True)
async def _cleanup_redis():
    """Delete budget/cooldown keys for projects created in this test."""
    from app.services import budget_service

    yield
    for project_id in _created_project_ids:
        await redis.delete(
            budget_service.window_key(project_id), f"alert:cooldown:{project_id}"
        )
    _created_project_ids.clear()


@pytest.fixture
async def client():
    """Async client driving the app in-process (no network, no lifespan)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db() -> AsyncSession:
    """A session against the test DB for direct assertions in tests."""
    async with db_base.async_session_factory() as session:
        yield session


@pytest.fixture
async def create_project(client):
    """Create a project via the real API (unauthenticated bootstrap) and
    return (project_id, raw_api_key)."""

    async def _create(name: str = "test", monthly: float = 70.0):
        resp = await client.post(
            "/v1/projects", json={"name": name, "monthly_budget_usd": monthly}
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        _created_project_ids.append(data["project"]["id"])
        return data["project"]["id"], data["api_key"]

    return _create