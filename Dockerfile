# syntax=docker/dockerfile:1

# ---- Base image ------------------------------------------------------------
# python:3.14-slim gives us the exact runtime we already develop against
# (matching local .venv) without build toolchains. slim = Debian without
# compilers/man pages - smaller attack surface and a much smaller image.
FROM python:3.14-slim

# ---- Workdir ----------------------------------------------------------------
# Every COPY/RUN below is relative to /app; also gives the app a stable,
# predictable location on disk regardless of who builds it.
WORKDIR /app

# ---- Dependencies first (the build-cache win) -------------------------------
# COPY only requirements.txt, THEN pip install. Docker caches layers; if
# requirements.txt is unchanged, this layer is reused on rebuilds and pip
# never re-runs. Copying source first would invalidate this cache on every
# code change, forcing a full pip install each rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Source -----------------------------------------------------------------
# The actual application code, plus alembic/ for migrations. .dockerignore
# keeps the build context small (no .venv, tests, .git, .env).
COPY . .

# ---- Port -------------------------------------------------------------------
# Document which port uvicorn listens on (Render maps this to its own public
# port). Not a firewall rule - just metadata for humans and cloud configs.
EXPOSE 8000

# ---- Runtime ----------------------------------------------------------------
# Shell-form CMD so $PORT is expanded: Render injects its own PORT env var and
# routes traffic to it (free tier assigns a random one). Locally we fall back
# to 8000. Slight trade-off vs exec-form (a shell wrapper), acceptable for
# deployability. uvicorn binds 0.0.0.0 because inside a container there is no
# localhost - traffic arrives on the container's external interface.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]