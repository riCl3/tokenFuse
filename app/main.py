from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import dashboard, projects, proxy
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

app.include_router(projects.router)
app.include_router(proxy.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"app": settings.app_name, "environment": settings.environment}