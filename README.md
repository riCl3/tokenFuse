<div align="center">

# TokenFuse

**LLM Cost-Control Gateway & Streaming Proxy**

Meter / Budget / Alert / Stream -- all in one reverse proxy.

---

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-7%20passing-brightgreen)](#testing)

[Overview](#overview) • [Features](#features) • [Architecture](#architecture) • [Quick Start](#quick-start) • [API Reference](#api-reference) • [Deployment](#deployment) • [Contributing](#contributing)

</div>

<br>

## Overview

TokenFuse is a per-project LLM spend control plane built with FastAPI, Redis, and PostgreSQL. It sits between your applications and LLM providers (OpenAI, OpenRouter) as a reverse proxy, giving you:

- **Per-project API key authentication** -- SHA-256 hashed keys with constant-time verification
- **Sliding-window budget enforcement** -- micro-USD precision, no sub-cent rounding errors
- **Real-time SSE streaming** -- disconnect-resilient usage accounting via background tap tasks
- **Burn-rate spike alerts** -- Telegram and webhook delivery with cooldown-gated deduplication
- **Operator dashboard** -- per-model cost breakdowns, 24h spend, live window state

A single runaway LLM loop can burn a monthly budget in minutes. TokenFuse gives you the circuit-breaker, the meter, and the alarm.

<br>

---

<br>

## Features

| Capability | Details |
|:--|:--|
| **Secure API Key Lifecycle** | `tfsk_` prefixed keys, SHA-256 hashed at rest, constant-time `hmac.compare_digest` verification. Raw key returned once at creation, never stored. |
| **Sliding-Window Budget** | Redis sorted-set window with Lua scripts (or pipeline fallback for Upstash). Micro-USD integer precision -- no floating-point drift. |
| **429 Budget Exceeded** | Structured `budget_exceeded` response with `used_units` / `budget_units`. Provider is never contacted once budget is gone. |
| **Warning Header** | `X-TokenFuse-Warning` header when spend crosses the configurable threshold (default 80%). |
| **SSE Streaming Proxy** | Full `text/event-stream` relay with `stream_options.include_usage` injection. OpenAI-compatible streaming out of the box. |
| **Disconnect-Resilient Billing** | Independent background tap task drains the upstream even after client disconnect. No budget loopholes. |
| **Burn-Rate Alerts** | Budget-baseline spike detection, per-project cooldown via `SET NX EX`, Telegram + webhook delivery. |
| **Operator Dashboard** | Per-project totals, per-model breakdowns, 24h spend, live Redis window state. All N+1-free queries. |
| **One-Click Deploy** | Docker Compose (4-service local stack) and Render Blueprint (free tier) included. |
| **Upstash Compatible** | Pipeline fallback when Redis Lua/EVAL is unavailable on cloud Redis. |

<br>

---

<br>

## Architecture

### Request Flow

```
                        ┌──────────────────────────────┐
                        │         FastAPI App           │
                        │                              │
 ┌─────────┐            │  ┌──────────────────────┐    │
 │         │  Bearer    │  │  Auth Guard           │    │
 │ Client  │  tfsk_...  │  │  SHA-256 hash lookup  │    │
 │   App   │ ──────────>│  └──────────┬───────────┘    │
 │         │            │             │                 │
 │         │ <──────────│  ┌──────────┴───────────┐    │
 │         │  JSON /    │  │  Budget Gate          │    │
 │         │  SSE       │  │  Redis sorted set     │    │
 └─────────┘            │  │  ok / warn / exceeded │    │
                        │  └──────────┬───────────┘    │
                        │             │                 │
                        │  ┌──────────┴───────────┐    │
                        │  │  Provider Client      │    │
                        │  │  httpx (pooled)       │    │
                        │  └──────────┬───────────┘    │
                        │             │                 │
                        └─────────────┼─────────────────┘
                                      │
                    ┌─────────────────┬┴──────────────────┐
                    ▼                                   ▼
           ┌────────────────┐                 ┌──────────────────┐
           │  Non-Streaming │                 │   SSE Streaming  │
           │  forward > JSON│                 │  tap > Queue >   │
           │                │                 │  StreamingResp.  │
           └───────┬────────┘                 └────────┬─────────┘
                   │                                   │
                   └──────────────┬────────────────────┘
                                  ▼
                        ┌──────────────────┐
                        │  Usage Recorder  │
                        │  Postgres + Redis │
                        └──────────────────┘
                                  ▲
                                  │
                        ┌──────────────────┐
                        │  Burn-Rate Alert │  <── APScheduler (60s)
                        │  Telegram/Webhook│
                        └──────────────────┘
```

### Data Flow

```
                    ┌─────────────────────┐
                    │     PostgreSQL 16    │
                    │                     │
                    │  projects           │
                    │  api_keys           │
                    │  usage_events       │
                    └─────────┬───────────┘
                              │
┌─────────────┐     ┌────────┴────────┐     ┌─────────────────┐
│             │────>│   TokenFuse     │────>│  OpenAI /        │
│  Your App   │     │   Gateway       │     │  OpenRouter      │
│             │<────│                 │<────│                  │
└─────────────┘     └────────┬────────┘     └─────────────────┘
                             │
                    ┌────────┴────────┐
                    │    Redis 7       │
                    │                  │
                    │  budget:<id>     │
                    │  alert:cooldown  │
                    └─────────────────┘
```

### Request Lifecycle

1. **Authentication** -- Client sends `Authorization: Bearer tfsk_...`. The guard hashes the key, looks up the `ApiKey` row, and loads the associated `Project` (eager-loaded via `selectinload`).

2. **Budget Check** -- Redis sliding window is pruned and summed atomically. Three outcomes:
   - `ok` -- proceed
   - `warn` -- proceed with `X-TokenFuse-Warning` header
   - `exceeded` -- HTTP 429, provider never contacted

3. **Forward to Provider** -- Request is forwarded via pooled `httpx.AsyncClient`. Unknown models return `$0` cost (flagged for review).

4. **Record Usage** -- Cost computed in micro-USD (`x 1,000,000`), added to Redis sorted set, and persisted as a `UsageEvent` row in PostgreSQL.

5. **Streaming Path** -- For `stream: true`, a background `_tap_stream` task independently drains the upstream SSE feed, captures the final usage chunk, and commits spend -- even if the client disconnects mid-stream.

<br>

---

<br>

## Quick Start

### Prerequisites

| Requirement | Version |
|:--|:--|
| Python | 3.14+ |
| PostgreSQL | 16 (Docker recommended) |
| Redis | 7 (Docker recommended) |
| pip | latest |

### 1. Clone & Install

```bash
git clone https://github.com/riCl3/tokenFuse.git
cd tokenFuse
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your values -- see Configuration section below
```

### 3. Start Databases

```bash
# PostgreSQL
docker run -d --name tokenfuse-pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:16-alpine

# Redis
docker run -d --name tokenfuse-redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 4. Run Migrations

```bash
alembic upgrade head
```

### 5. Start the Server

```bash
uvicorn app.main:app --reload --port 8000
```

The API is live at **http://localhost:8000**. Interactive docs at **http://localhost:8000/docs**.

### 6. Bootstrap a Project

```bash
curl -X POST http://localhost:8000/v1/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "my-project", "monthly_budget_usd": 50.0}'
```

The response includes the raw `api_key`. **Save it -- it will not be shown again.**

<br>

---

<br>

## Docker Compose

The fastest way to run the full stack (app + Postgres + Redis + mock provider):

```bash
docker compose up --build
```

### Services

| Service | Description | Port |
|:--|:--|:--|
| `app` | TokenFuse gateway | `8000` (published) |
| `db` | PostgreSQL 16 | `5432` (internal) |
| `redis` | Redis 7 | `6379` (internal) |
| `mock` | Mock OpenAI provider | `8200` (internal) |

Only `app:8000` is exposed externally. All other services communicate over the internal Docker network.

### Common Commands

```bash
# Run migrations inside the container
docker compose exec app alembic upgrade head

# Follow logs
docker compose logs -f app

# Stop (data persists in named volumes)
docker compose down

# Stop AND delete data
docker compose down -v
```

<br>

---

<br>

## Configuration

All configuration is via environment variables (loaded from `.env` in development).

### Core

| Variable | Default | Description |
|:--|:--|:--|
| `APP_NAME` | `TokenFuse` | Application name |
| `ENVIRONMENT` | `development` | Runtime environment |
| `LOG_LEVEL` | `INFO` | Python logging level |

### Database

| Variable | Default | Description |
|:--|:--|:--|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/tokenfuse` | Async PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `REDIS_EVAL_AVAILABLE` | `true` | Set `false` for Upstash (no Lua/EVAL support) |

### Provider Keys

| Variable | Default | Description |
|:--|:--|:--|
| `OPENAI_API_KEY` | `""` | OpenAI API key (used upstream by TokenFuse) |
| `OPENROUTER_API_KEY` | `""` | OpenRouter API key |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI base URL (override for compatible providers) |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter base URL |
| `PROVIDER_TIMEOUT_SECONDS` | `120.0` | HTTP timeout for upstream calls |

### Budget Defaults

| Variable | Default | Description |
|:--|:--|:--|
| `DEFAULT_MONTHLY_BUDGET_USD` | `50.0` | Default monthly budget for new projects |
| `BUDGET_WARN_PCT` | `0.8` | Warning threshold (80% of budget) |
| `BUDGET_WINDOW_SECONDS` | `3600` | Sliding window duration (1 hour) |
| `FALLBACK_MODEL` | `""` | Fallback model if request model is unknown |

### Burn-Rate Alerts

| Variable | Default | Description |
|:--|:--|:--|
| `TELEGRAM_BOT_TOKEN` | `""` | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | `""` | Telegram chat ID for alerts |
| `ALERT_WEBHOOK_URL` | `""` | Webhook URL for alerts (JSON POST) |
| `ALERT_RECENT_WINDOW_SECONDS` | `300` | Lookback window for spike detection |
| `ALERT_SPIKE_MULTIPLIER` | `5.0` | Spike threshold multiplier |
| `ALERT_MIN_SPEND_USD` | `0.50` | Minimum spend floor before alerting |
| `ALERT_COOLDOWN_SECONDS` | `900` | Per-project cooldown between alerts |
| `ALERT_CHECK_INTERVAL_SECONDS` | `60` | Scheduler check interval |

<br>

---

<br>

## API Reference

All endpoints require `Authorization: Bearer tfsk_...` header unless noted otherwise.

---

#### `POST /v1/projects`

Bootstrap a new project. **No auth required.**

**Request:**

```json
{
  "name": "my-project",
  "monthly_budget_usd": 50.0,
  "warn_pct": 0.8,
  "fallback_model": "gpt-4o-mini"
}
```

**Response (201):**

```json
{
  "project": {
    "id": 1,
    "name": "my-project",
    "monthly_budget_usd": 50.0,
    "warn_pct": 0.8,
    "fallback_model": "gpt-4o-mini",
    "is_active": true,
    "created_at": "2026-08-21T12:00:00Z",
    "api_keys": []
  },
  "api_key": "tfsk_abc123..."
}
```

> **Note:** The `api_key` is shown **only once**. Store it securely.

---

#### `GET /v1/projects/{project_id}`

Returns project details. Ownership check enforced -- your key must belong to this project.

---

#### `POST /v1/chat/completions`

OpenAI-compatible chat completions endpoint. Supports both buffered and streaming responses.

**Non-streaming request:**

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "Hello, world!"}
  ]
}
```

**Streaming request:**

```json
{
  "provider": "openai",
  "model": "gpt-4o",
  "messages": [
    {"role": "user", "content": "Hello, world!"}
  ],
  "stream": true
}
```

**Response behavior:**

| Status | Meaning |
|:--|:--|
| `200` | Provider response returned (JSON or SSE stream) |
| `429` | Budget exceeded -- `budget_exceeded` detail with `used_units` / `budget_units` |
| `502` | Upstream provider unreachable or returned an error |

When spend approaches the budget limit, the response includes an `X-TokenFuse-Warning` header.

---

#### `GET /v1/projects`

Returns all projects with aggregated totals (requests, cost, tokens) and live Redis window state.

**Response:**

```json
[
  {
    "id": 1,
    "name": "my-project",
    "monthly_budget_usd": 50.0,
    "is_active": true,
    "total_requests": 142,
    "total_cost_usd": 12.34,
    "total_tokens": 284000,
    "window_used_units": 12340000,
    "window_budget_units": 13888888,
    "window_status": "ok"
  }
]
```

---

#### `GET /v1/usage/{project_id}`

Detailed usage breakdown for a single project.

**Response:**

```json
{
  "project_id": 1,
  "project_name": "my-project",
  "totals": {
    "requests": 142,
    "cost_usd": 12.34,
    "total_tokens": 284000
  },
  "by_model": [
    {
      "model": "gpt-4o",
      "requests": 100,
      "cost_usd": 10.50,
      "total_tokens": 200000
    },
    {
      "model": "gpt-4o-mini",
      "requests": 42,
      "cost_usd": 1.84,
      "total_tokens": 84000
    }
  ],
  "last_24h_cost_usd": 5.67,
  "window_used_units": 5670000,
  "window_budget_units": 13888888,
  "window_status": "ok"
}
```

---

#### `GET /health`

Health check endpoint. **No auth required.**

```json
{
  "app": "TokenFuse",
  "environment": "development"
}
```

<br>

---

<br>

## Database Schema

### `projects`

| Column | Type | Notes |
|:--|:--|:--|
| `id` | `integer` | Primary key, auto-increment |
| `name` | `string(120)` | Project name |
| `monthly_budget_usd` | `numeric(12,2)` | Monthly budget in USD |
| `warn_pct` | `float` | Warning threshold (0--1) |
| `fallback_model` | `string(120)` | Nullable. Fallback model |
| `is_active` | `bool` | Active flag |
| `created_at` | `datetime(tz)` | UTC creation timestamp |

### `api_keys`

| Column | Type | Notes |
|:--|:--|:--|
| `id` | `integer` | Primary key, auto-increment |
| `project_id` | `integer` | FK to `projects`, cascade delete |
| `label` | `string(60)` | Nullable. Key label |
| `key_hash` | `string(64)` | SHA-256 hash of the raw key. Unique. |
| `is_active` | `bool` | Active flag |
| `created_at` | `datetime(tz)` | UTC creation timestamp |
| `last_used_at` | `datetime(tz)` | Nullable. Last usage timestamp |

### `usage_events`

| Column | Type | Notes |
|:--|:--|:--|
| `id` | `integer` | Primary key, auto-increment |
| `project_id` | `integer` | FK to `projects`, cascade delete |
| `api_key_id` | `integer` | FK to `api_keys`, nullable, set null on delete |
| `provider` | `string(30)` | Provider name |
| `model` | `string(120)` | Model identifier |
| `prompt_tokens` | `integer` | Input token count |
| `completion_tokens` | `integer` | Output token count |
| `total_tokens` | `integer` | Total token count |
| `cost_usd` | `numeric(12,6)` | Cost in USD |
| `request_id` | `string(120)` | Nullable. Provider request ID |
| `streamed` | `bool` | Whether this was a streaming request |
| `created_at` | `datetime(tz)` | UTC creation timestamp |

**Index:** `ix_usage_events_project_created` on `(project_id, created_at)`

<br>

---

<br>

## Budget Model

TokenFuse uses a **sliding window** budget model with **micro-USD** precision.

### How It Works

1. **Monthly budget is prorated** to the window duration:
   ```
   window_budget = monthly_budget x window_seconds / (30 x 24 x 3600) x 1,000,000
   ```

2. **Each API call** adds a member to a Redis sorted set (`budget:<project_id>`) with the score set to the event timestamp in milliseconds.

3. **On each check**, expired entries outside the window are pruned (`ZREMRANGEBYSCORE`), and the remaining sum is computed.

### Budget Proration Examples

| Monthly Budget | Window (1hr) | Window Budget (micro-USD) |
|:--|:--|:--|
| $1 | 3600s | 1,388 |
| $50 | 3600s | 69,444 |
| $70 | 3600s | 97,222 |

A single `gpt-4o` call with 5k input + 3k output tokens costs **42,500 micro-USD** ($0.0425). With a $70/month budget, you can make approximately 2 calls per hour before hitting the window cap.

### Redis Atomicity

| Environment | Strategy | Notes |
|:--|:--|:--|
| Local Redis 7 | Lua scripts | Atomic prune + sum in 2 round trips |
| Upstash / Cloud Redis | Pipeline fallback | No EVAL support. Slightly weaker atomicity, acceptable for MVP. |

<br>

---

<br>

## Testing

The test suite uses **pytest-asyncio** with real PostgreSQL and Redis (no mocking of DB or cache).

### Setup

```bash
# Create test database
docker exec tokenfuse-pg psql -U postgres -c "CREATE DATABASE tokenfuse_test;"

# Run tests
pytest -v
```

### Test Coverage

| Test | Verifies |
|:--|:--|
| `test_missing_key_401` | No `Authorization` header returns 401 + `WWW-Authenticate: Bearer` |
| `test_invalid_key_401` | Invalid key returns 401 |
| `test_auth_success` | Valid key returns 200 with project data |
| `test_cross_project_403` | Key from project A accessing project B returns 403 |
| `test_budget_exceeded_429` | Spend exceeding window budget returns 429; provider is not called |
| `test_non_streaming_success_records_usage` | Non-streaming completion creates a Postgres row + Redis event |
| `test_streaming_forwards_and_records` | SSE stream forwards all chunks and records usage |

### Test Infrastructure

| Component | Approach |
|:--|:--|
| LLM Provider | **RespX** mocks -- no real API keys needed |
| Event Loop | **Session-scoped** to avoid cross-loop `asyncpg` issues |
| Cleanup | **Autouse fixture** deletes Redis keys after each test |

<br>

---

<br>

## Project Structure

```
tokenFuse/
|
|-- app/
|   |-- api/
|   |   |-- deps.py                 # Auth guard (get_current_project)
|   |   |-- routes/
|   |       |-- dashboard.py        # Operator dashboard endpoints
|   |       |-- projects.py         # Project CRUD
|   |       |-- proxy.py            # Chat completions proxy (stream + non-stream)
|   |
|   |-- core/
|   |   |-- config.py               # Settings (pydantic-settings)
|   |   |-- pricing.py              # Model pricing map + cost estimation
|   |   |-- redis_client.py         # Async Redis client
|   |   |-- security.py             # API key generation, hashing, verification
|   |
|   |-- db/
|   |   |-- base.py                 # Async engine, session factory, Base
|   |   |-- deps.py                 # get_db dependency (session per request)
|   |   |-- models.py               # Project, ApiKey, UsageEvent models
|   |
|   |-- schemas/
|   |   |-- dashboard.py            # Dashboard response schemas
|   |   |-- project.py              # Project request/response schemas
|   |   |-- proxy.py                # Chat completion request schema
|   |
|   |-- services/
|   |   |-- alert_service.py        # Burn-rate spike detection + delivery
|   |   |-- budget_service.py       # Sliding-window budget (Redis)
|   |   |-- project_service.py      # Project creation + lookup
|   |   |-- provider_client.py      # httpx provider forwarding
|   |   |-- usage_service.py        # UsageEvent persistence + aggregation
|   |
|   |-- main.py                     # FastAPI app, lifespan, router registration
|
|-- alembic/                        # Database migrations
|   |-- versions/                   # Migration scripts
|
|-- scripts/
|   |-- demo_budget.py              # Standalone budget demo
|   |-- mock_provider.py            # Mock OpenAI provider for testing
|   |-- webhook_receiver.py         # Local webhook test endpoint
|
|-- tests/
|   |-- conftest.py                 # Shared fixtures (DB, Redis, client)
|   |-- test_auth.py                # Authentication tests
|   |-- test_budget.py              # Budget enforcement + proxy tests
|   |-- test_streaming.py           # SSE streaming tests
|
|-- docs/                           # Detailed development docs (18 guides)
|-- Dockerfile                      # Production Docker build
|-- docker-compose.yml              # 4-service local deployment
|-- render.yaml                     # Render Blueprint (free tier deploy)
|-- alembic.ini                     # Alembic configuration
|-- requirements.txt                # Python dependencies
|-- pytest.ini                      # Test configuration
|-- .env.example                    # Environment variable template
|-- .gitignore                      # Git ignore rules
|-- .dockerignore                   # Docker ignore rules
```

<br>

---

<br>

## Security

### API Key Lifecycle

| Stage | Mechanism |
|:--|:--|
| **Generation** | `tfsk_` prefix + 32 bytes of `secrets.token_urlsafe()` -- high entropy, URL-safe |
| **Storage** | Only the SHA-256 hash is stored in PostgreSQL. Raw key returned **once** at creation. |
| **Verification** | Constant-time comparison via `hmac.compare_digest` -- immune to timing attacks |
| **Transmission** | `Authorization: Bearer tfsk_...` header on every request |

### Design Decisions

- **No bcrypt/scrypt** -- Keys are already high-entropy random tokens; slow KDFs add latency without meaningful security benefit
- **No salt needed** -- Every key is unique, so no two hashes can be compared
- **`.env` gitignored** -- Secrets are never committed to version control
- **`sync: false` in Render** -- Deployment secrets are prompted for, not stored in code

### Access Control

| Condition | Response |
|:--|:--|
| Missing or invalid API key | `401 Unauthorized` |
| Disabled API key | `403 Forbidden` |
| Disabled project | `403 Forbidden` |
| Cross-project key usage | `403 Forbidden` |

<br>

---

<br>

## Deployment

### Docker Compose (Local / Self-Hosted)

```bash
docker compose up --build -d
docker compose exec app alembic upgrade head
```

### Render (Free Tier)

1. Push to GitHub
2. Go to **Render Dashboard** > **New** > **Blueprint**
3. Select your repo -- Render reads `render.yaml` automatically
4. Fill in the prompted secrets:
   - `DATABASE_URL` -- Neon Postgres connection string
   - `REDIS_URL` -- Upstash Redis URL (TLS)
   - `OPENAI_API_KEY` -- Your OpenAI key
   - Alert credentials (optional)
5. Run migration locally against the Neon URL:
   ```bash
   DATABASE_URL="your-neon-url?ssl=require" alembic upgrade head
   ```

### Production Checklist

- [ ] Set `ENVIRONMENT=production`
- [ ] Set `REDIS_EVAL_AVAILABLE=false` if using Upstash
- [ ] Configure at least one alert channel (Telegram or webhook)
- [ ] Set appropriate `DEFAULT_MONTHLY_BUDGET_USD` for new projects
- [ ] Run `alembic upgrade head` against production database
- [ ] Verify `/health` endpoint returns 200

<br>

---

<br>

## Supported Models

TokenFuse includes built-in pricing for these models:

| Model | Input ($/1M tokens) | Output ($/1M tokens) |
|:--|--:|--:|
| `gpt-4o` | $2.50 | $10.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |
| `gpt-4.1` | $2.00 | $8.00 |
| `gpt-4.1-mini` | $0.40 | $1.60 |
| `gpt-3.5-turbo` | $0.50 | $1.50 |
| `claude-3-5-sonnet-20241022` | $3.00 | $15.00 |
| `claude-3-5-haiku-20241022` | $0.80 | $4.00 |

Unknown models default to `$0` cost (flagged in logs for review).

<br>

---

<br>

## Roadmap

- [ ] tiktoken fallback -- token counting for providers that omit usage chunks
- [ ] Admin/operator auth -- dedicated admin key type for dashboard access
- [ ] Per-project alert overrides -- severity tiers, time-of-day baselines
- [ ] Multi-worker safety -- Redis SETNX leader lock for alert scheduler
- [ ] Rate limiting per API key -- request-rate caps (not just budget)
- [ ] Usage export -- CSV/JSON billing report download
- [ ] Caching layer -- cache repeat prompt completions
- [ ] Alembic test DB migration -- replace `create_all` with proper migrations

<br>

---

<br>

## Contributing

Contributions are welcome.

### Development Setup

```bash
git clone https://github.com/riCl3/tokenFuse.git
cd tokenFuse

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

# Start databases (Docker)
docker run -d --name tokenfuse-pg \
  -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 postgres:16-alpine

docker run -d --name tokenfuse-redis -p 6379:6379 redis:7-alpine

alembic upgrade head

# Create test database
docker exec tokenfuse-pg psql -U postgres -c "CREATE DATABASE tokenfuse_test;"

# Run tests
pytest -v
```

### Code Style

| Convention | Details |
|:--|:--|
| **Python version** | 3.14+ features welcome (type unions with `\|`, `match` statements, etc.) |
| **Async-first** | All I/O is async (`asyncpg`, `httpx`, `redis.asyncio`) |
| **Schemas** | Pydantic v2 for all request/response models |
| **ORM** | SQLAlchemy 2.0 async patterns (mapped columns, `select()` style) |
| **Failure handling** | Bookkeeping failures are non-fatal -- a usage recording error should never break an LLM request that already succeeded |

### Pull Request Guidelines

1. Fork the repo and create a feature branch from `main`
2. Write tests for new functionality (`tests/`)
3. Ensure all tests pass: `pytest -v`
4. Keep PRs focused -- one feature or fix per PR
5. Update documentation if adding new endpoints or configuration

### Reporting Issues

Use GitHub Issues for bug reports and feature requests. Include:
- Steps to reproduce
- Expected behavior vs actual behavior
- Python version, OS, and relevant dependency versions

<br>

---

<br>

## Documentation

The `docs/` directory contains 18 detailed development guides:

| # | Guide | Topic |
|:--|:--|:--|
| 01 | Project Overview | High-level architecture and goals |
| 02 | Project Structure | File and directory organization |
| 03 | Configuration Management | Settings, env vars, pydantic-settings |
| 04 | Database Fundamentals | Async engine, sessions, connection pooling |
| 05 | SQLAlchemy Models | Project, ApiKey, UsageEvent definitions |
| 06 | Alembic Migrations | Schema versioning and migration workflow |
| 07 | Dependency Injection | FastAPI Depends, get_db, get_current_project |
| 08 | API Routes & Schemas | Request/response models, validation |
| 09 | Services Layer | Business logic separation |
| 10 | API Key Security | Generation, hashing, verification |
| 11 | Redis Budget Tracking | Sliding window, Lua scripts, micro-USD |
| 12 | HTTP Proxy | Provider forwarding, error handling |
| 13 | SSE Streaming | Server-Sent Events, tap/queue/shield pattern |
| 14 | Background Jobs & Alerts | APScheduler, spike detection, delivery |
| 15 | Usage Dashboard | Aggregation queries, operator views |
| 16 | Testing | pytest-asyncio, fixtures, mocking |
| 17 | Containerization & Deployment | Docker, Compose, Render Blueprint |
| 18 | Request Lifecycle | End-to-end request walkthrough |

<br>

---

<br>

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<br>

## Acknowledgments

Built with [FastAPI](https://fastapi.tiangolo.com/), [SQLAlchemy](https://www.sqlalchemy.org/), [Redis](https://redis.io/), [Alembic](https://alembic.sqlalchemy.org/), [Pydantic](https://docs.pydantic.dev/), [httpx](https://www.python-httpx.org/), [APScheduler](https://apscheduler.readthedocs.io/), and [Docker](https://www.docker.com/).

<br>

<div align="center">

**Built for teams that need control over their LLM spend.**

[Back to Top](#tokenfuse)

</div>
