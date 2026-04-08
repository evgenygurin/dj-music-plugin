# DJ Music Plugin — FastAPI/MCP backend container for Fly.io.
#
# Two-stage build:
#   1. builder — installs uv + project dependencies into a venv at /app/.venv
#   2. runtime — copies the venv + source, runs uvicorn against app.api.server:api
#
# Skipped extras: stems (demucs/torch ~2GB), postgres (pgvector — Supabase
# already provides it server-side), otel (only needed if Sentry/OTEL set).
#
# Audio extra is included so analyze_track / classify_mood work in the cloud.
# Filesystem-bound tools (download_tracks, deliver_set) require a writable
# volume mounted at /data and the DJ_YM_LIBRARY_PATH env var.

ARG PYTHON_VERSION=3.12

# ── builder ────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

# uv installs faster than pip and respects pyproject.toml/lock
COPY --from=ghcr.io/astral-sh/uv:0.6.6 /uv /uvx /usr/local/bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# librosa/soundfile need libsndfile + ffmpeg at runtime; build essentials only
# during install for any wheels that fall through to source build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libsndfile1 \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (cached layer) — only re-runs when pyproject/lock change
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra http --extra audio

# Now install the project itself (re-runs on app code changes only)
COPY app ./app
COPY app/api/server.py ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra http --extra audio


# ── runtime ────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

# Runtime libs only (no build-essential, no caches)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libsndfile1 \
        ffmpeg \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Copy the prebuilt venv + project from the builder stage
COPY --from=builder /app /app

# Fly.io routes external 80/443 → internal 8080 (see fly.toml)
EXPOSE 8080

# uvicorn directly — no `uv run` wrapper since the venv is already activated
# via PATH. --proxy-headers is required because Fly's edge terminates TLS.
CMD ["uvicorn", "app.api.server:api", \
     "--host", "0.0.0.0", \
     "--port", "8080", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
