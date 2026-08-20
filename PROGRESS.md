# TokenFuse — Progress

## What's built
- **Phase 2 — App configuration**
  - `app/core/config.py`: `Settings` class (pydantic-settings) with database URL, redis URL,
    provider API keys, telegram/webhook alert creds, budget defaults.
  - `get_settings()` singleton via `@lru_cache` — config read once, reused everywhere.
  - `app/main.py`: minimal FastAPI app wired to settings; `lifespan` prints app name on
    startup; `/health` endpoint returns app name + environment from settings.
  - Scaffolding: `app/` package, `requirements.txt`, `.env.example` (tracked),
    `.env` (gitignored), `.gitignore`.

- **Phase 3 — Database layer**
  - `app/db/base.py`: async engine (`create_async_engine`), `async_session_factory`,
    `Base` (DeclarativeBase), and `get_session()` dependency generator for future routes.
  - `app/db/models.py`: `Project`, `ApiKey`, `UsageEvent` with integer PKs, FKs with
    `ondelete` actions, `key_hash` unique, composite index `(project_id, created_at)`,
    `cascade="all, delete-orphan"` on project relationships, timezone-aware timestamps.
  - Alembic set up (async template), wired to `Settings.database_url` + `Base.metadata`.
    First migration applied: `f5ba9156594b` (tables: projects, api_keys, usage_events).
  - Docker Postgres 16 container `tokenfuse-pg` running on localhost:5432.
  - Smoke-tested: insert/commit/read-back (eager-loaded relationships)/cascade-delete.

- **Phase 4 — Project + API key CRUD**
  - `app/schemas/project.py`: Pydantic v2 schemas — `ProjectCreate`, `ProjectResponse`,
    `ApiKeySummary`, `ProjectCreatedResponse` (create vs response kept separate).
  - `app/db/deps.py`: `get_db` yield-dependency (session-per-request via `Depends`).
    `get_session` removed from `base.py` in favor of `get_db`.
  - `app/services/project_service.py`: `create_project` (defaults from settings,
    `tfsk_` key via `secrets.token_urlsafe`, SHA-256 hash stored, plaintext returned once),
    `get_project` (eager-loads api_keys).
  - `app/api/routes/projects.py`: `POST /v1/projects` (201, returns project + raw key),
    `GET /v1/projects/{id}` (404 if missing). Router registered in `main.py`.
  - Live-verified: create (defaults + overrides), get, 404. Raw key confirmed NOT stored.

- **Phase 5 — Authentication**
  - `app/core/security.py`: `generate_api_key` (`tfsk_` + `secrets.token_urlsafe(32)`),
    `hash_api_key` (SHA-256), `verify_api_key` (constant-time `hmac.compare_digest`).
    Chosen over bcrypt: keys are high-entropy, so slow KDFs buy nothing; no salt needed
    (every key unique). Moved out of `project_service` into core for reuse/tests.
  - `app/api/deps.py`: `get_current_project` guard — parses `Authorization: Bearer`
    via `HTTPBearer(auto_error=False)`, hashes presented key, looks up `ApiKey` by
    `key_hash` (eager-loading project + its keys), returns `AuthContext(project, api_key)`.
    Error pattern: missing/invalid key -> 401 + `WWW-Authenticate` header; disabled
    key/project -> 403; ownership mismatch -> 403.
  - `GET /v1/projects/{id}` now protected; route uses `AuthContext` from the guard
    (no separate session — single dependency does auth + data loading). Ownership
    check rejects cross-project access.
  - `service.get_project` kept (currently unused by routes; for later admin/dashboard).
  - Live-tested: 200 own-key, 401 no-key, 401 bad-key, 403 cross-project, unauthenticated
    POST bootstrap still open.

- **Phase 6 — Redis sliding-window budget tracking**
  - `app/core/redis_client.py`: single async `Redis` client from `settings.redis_url`
    (`decode_responses=True`).
  - `app/services/budget_service.py`: sliding window over a sorted set
    (member = `<event_id>:<cents>`, score = timestamp ms). Two Lua scripts:
    `record` (atomic prune + ZADD) and `window_total` (atomic prune + sum).
    `check_budget` -> `BudgetStatus(status, used_cents, budget_cents)` with
    ok / warn (>= warn_pct) / exceeded (>= budget). Window budget prorated from
    the project's monthly budget: `monthly * window / (30*24*3600)`.
  - `scripts/demo_budget.py`: standalone demo (no API/DB). Verified live:
    OK -> WARN -> EXCEEDED at thresholds, spend keeps counting mid-window
    (no fixed-window boundary reset), old events pruned once window slides.
  - Redis 7 Docker container `tokenfuse-redis` on localhost:6379.
  - `budget_window_seconds` setting added (default 3600).

- **Phase 7a — Non-streaming proxy**
  - `budget_service` refactored to micro-USD units (USD * 1e6) — sub-cent LLM
    costs no longer round to zero. Demo script updated to match.
  - `app/core/pricing.py`: `MODEL_PRICING` map (USD per 1M tokens) +
    `estimate_cost_usd`. Unknown model -> $0 (flag for later).
  - `app/services/provider_client.py`: shared `httpx.AsyncClient` (pooled, closed on
    shutdown), `forward_chat_completion` -> `CompletionResult(data, usage)`; skips
    `Authorization` header when the provider key is empty (fixes `LocalProtocolError`
    on the trailing-space header). `close()` wired into lifespan.
  - `app/schemas/proxy.py` + `app/api/routes/proxy.py`: `POST /v1/chat/completions` —
    auth guard -> budget check (429 structured when exceeded, `X-TokenFuse-Warning`
    at warn) -> forward -> record usage AFTER success. Provider errors -> 502.
  - `scripts/mock_provider.py`: fake OpenAI provider (fixed 8k-token usage) for
    testing without real keys.
  - Live-verified end to end: project w/ $70 monthly (hourly window budget
    97,222 units) -> req1 ok, req2 ok, req3 warn header, req4 429; Redis window
    showed 3 x 42,500-unit events.
- **Phase 7b — SSE streaming proxy**
  - `provider_client.stream_chat_completion`: httpx `client.stream` +
    `aiter_bytes()` yields upstream SSE bytes without buffering.
  - `scripts/mock_provider.py`: mock now streams word-by-word SSE chunks
    (200ms pause), a finish chunk, a usage chunk, and `[DONE]`.
  - Route: dispatches on `stream: true`, injects
    `stream_options: {"include_usage": true}`, returns `StreamingResponse`.
    Return type changed to `Response` (union of two response classes is not a
    valid Pydantic response field).
  - Usage for streams: read the final usage chunk (strategy (a)). tiktoken
    fallback (b) deferred; likely blocked on Python 3.14 wheels.
  - Disconnect handling: upstream read moved into an INDEPENDENT background
    task (`_tap_stream`) feeding an `asyncio.Queue`; the generator only
    relays. On client disconnect Starlette cancels the generator, but the
    tracked tap (module-level `_active_taps` strong-ref set; the event loop
    only keeps weak refs) keeps draining, captures the usage chunk, and
    commits the spend. `asyncio.shield` used in the generator finally.
    First attempt (shield only around a commit inside the generator) FAILED:
    cancellation propagates into the upstream read and closes it, so the usage
    chunk was discarded before it arrived.
  - Live-verified: normal stream forwards all 9 events + records 42,500 units;
    client killed mid-stream still records the full 42,500 units.

## What's next
- Phase 7c: tiktoken fallback for providers that omit the usage chunk.
- Burn-rate alerts (APScheduler + Telegram/webhook), dashboard endpoints,
  Postgres `usage_events` persistence (TODO marker already in proxy route).

## Open decisions
- Upstash Redis (deploy target) historically does NOT support Lua/EVAL scripts.
  Options: self-host Redis on Render, or rework to `MULTI/EXEC`+`WATCH`/counter
  approach for Upstash. Pending when we get to deployment.
- Window budget derived from monthly budget (hourly cap = monthly/720). Revisit
  if projects need explicit short-window caps.

## Open decisions
- Env vars: no `TOKENFUSE_` prefix (decided).
- Model->price map lives in a code constant for now (decided); may become a table later.
- Local Postgres: Docker container `tokenfuse-pg` (decided).
- Timestamps: timezone-aware columns (`DateTime(timezone=True)`), UTC from Python (decided).
- Hard-deleting projects cascades to keys+events. For real data we'll prefer
  `is_active=False` soft-disable; revisit when building admin routes.