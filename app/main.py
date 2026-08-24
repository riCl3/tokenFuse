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