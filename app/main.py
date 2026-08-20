from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[startup] {settings.app_name} booting in {settings.environment} mode")
    yield
    print(f"[shutdown] {settings.app_name} shutting down")


app = FastAPI(title=settings.app_name, lifespan=lifespan)


@app.get("/health")
async def health():
    return {"app": settings.app_name, "environment": settings.environment}