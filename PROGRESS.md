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

## What's next
- Reverse proxy + SSE aggregation (httpx forwarding to providers).
- Burn-rate alerts (APScheduler + Telegram/webhook), dashboard endpoints.

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