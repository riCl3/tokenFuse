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

## What's next
- Database layer: SQLAlchemy 2.0 async engine + session + models (projects, budgets).
- Then: Redis sliding-window counters, reverse proxy + SSE, auth, alerts, dashboard.

## Open decisions
- Env vars: no `TOKENFUSE_` prefix (decided).
- `DATABASE_URL` default points at localhost; production values go in `.env` (gitignored).
- Whether to add a per-provider model config (cheaper-model fallback) — pending when we build
  the proxy/budget phases.