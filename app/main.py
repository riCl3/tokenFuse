from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import projects, proxy
from app.core.config import get_settings
from app.services import provider_client

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[startup] {settings.app_name} booting in {settings.environment} mode")
    print(f"[startup] provider openai -> {settings.openai_base_url}")
    yield
    await provider_client.close()
    print(f"[shutdown] {settings.app_name} shutting down")


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.include_router(projects.router)
app.include_router(proxy.router)


@app.get("/health")
async def health():
    return {"app": settings.app_name, "environment": settings.environment}