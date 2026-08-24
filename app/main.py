from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, dashboard, pricing, projects, proxy
from app.core.config import get_settings
from app.services import alert_service, provider_client

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[startup] {settings.app_name} booting in {settings.environment} mode")
    print(f"[startup] provider openai -> {settings.openai_base_url}")

    # Auto-migrate: ensure all tables exist and add missing columns
    from app.db.base import Base, engine
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add owner_id to projects if missing (safe for existing DBs)
        await conn.execute(text(
            "ALTER TABLE projects ADD COLUMN IF NOT EXISTS owner_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_projects_owner_id ON projects (owner_id)"
        ))
    print("[startup] database tables verified")

    scheduler = alert_service.create_scheduler()
    scheduler.start()
    print(
        f"[startup] burn-rate alert scheduler started "
        f"(check every {settings.alert_check_interval_seconds}s, "
        f"recent window {settings.alert_recent_window_seconds}s, "
        f"spike >= {settings.alert_spike_multiplier}x budget rate)"
    )

    try:
        yield
    finally:
        # Stop the scheduler BEFORE closing shared clients it depends on.
        scheduler.shutdown(wait=False)
        print("[shutdown] burn-rate alert scheduler stopped")
        await provider_client.close()
        print(f"[shutdown] {settings.app_name} shutting down")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# TEMPORARY: surface 500 details for debugging (remove after)
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def debug_exception_handler(request, exc):
    import traceback
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "trace": traceback.format_exc()[-1500:]},
    )

# CORS origins come from env CORS_ORIGINS (comma-separated). Regex covers all Vercel preview/prod domains.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(pricing.router)
app.include_router(proxy.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"app": settings.app_name, "environment": settings.environment}


@app.get("/debug/db-check")
async def debug_db_check():
    """TEMPORARY diagnostic — remove after debugging. Checks projects table schema."""
    from app.db.base import engine
    from sqlalchemy import text
    async with engine.connect() as conn:
        cols = (
            await conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='projects' ORDER BY ordinal_position"
            ))
        ).scalars().all()
        tables = (
            await conn.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema='public' ORDER BY table_name"
            ))
        ).scalars().all()
        return {"projects_columns": cols, "tables": tables}