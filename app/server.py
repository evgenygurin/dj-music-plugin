"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py             # production

    # With OpenTelemetry (requires `uv sync --extra otel`):
    opentelemetry-instrument \\
      --service_name dj-music \\
      --exporter_otlp_endpoint http://localhost:4317 \\
      fastmcp run app/server.py

    # Or via environment variables:
    export OTEL_SERVICE_NAME=dj-music
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
    opentelemetry-instrument fastmcp run app/server.py
"""

import logging
import os

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

# ── Observability Setup ──────────────────────────────

logger = logging.getLogger(__name__)

# Configure Sentry if DSN provided
if settings.sentry_dsn or os.getenv("SENTRY_DSN"):
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn or os.getenv("SENTRY_DSN"),
            traces_sample_rate=0.1 if not settings.debug else 1.0,
            profiles_sample_rate=0.1 if not settings.debug else 1.0,
            environment="development" if settings.debug else "production",
        )
        logger.info("Sentry error tracking enabled")
    except ImportError:
        logger.warning(
            "SENTRY_DSN configured but sentry-sdk not installed. "
            "Install with: uv sync --extra sentry"
        )

# OpenTelemetry is configured externally via opentelemetry-instrument
# or programmatically by the user. FastMCP uses opentelemetry-api which
# is a no-op unless an SDK is configured.
#
# To enable OTEL:
# 1. Install: uv sync --extra otel
# 2. Run with: opentelemetry-instrument --service_name dj-music fastmcp run app/server.py
# 3. Or set OTEL_SERVICE_NAME and OTEL_EXPORTER_OTLP_ENDPOINT env vars
#
# FastMCP will automatically create spans for tool/resource/prompt operations.
# Custom spans for heavy operations are added via @instrument_heavy_operation decorator.

# ── Lifespans ────────────────────────────────────────


@lifespan
async def db_lifespan(server):  # type: ignore[no-untyped-def]
    """Database engine + session factory lifecycle."""
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield {"db_engine": engine, "db_session_factory": session_factory}
    finally:
        await engine.dispose()


# ── Server ───────────────────────────────────────────

mcp = FastMCP(
    name=settings.server_name,
    instructions=(
        "DJ techno music library management, set building, "
        "and Yandex Music integration. "
        "Use unlock_tools to access hidden tool categories."
    ),
    lifespan=db_lifespan,
    list_page_size=settings.pagination_size,
    on_duplicate="error",
)

# ── Middleware Pipeline ──────────────────────────────
# Order: outermost (first added) → innermost (last added)
# Request flows: first → ... → last → tool handler
# Response flows: tool handler → last → ... → first

from app.middleware import DetailedTimingMiddleware, StructuredLoggingMiddleware

# Outermost: structured logging captures all requests
mcp.add_middleware(StructuredLoggingMiddleware())

# Innermost: detailed timing measures actual tool execution
mcp.add_middleware(DetailedTimingMiddleware())

# ── Component Visibility ─────────────────────────────

# Hide audio tools at startup (require explicit unlock)
mcp.disable(tags={"audio"})

# ── FileSystemProvider auto-discovers tools/resources/prompts ─
# When running via `fastmcp run app/server.py`, FastMCP auto-discovers
# decorated functions in the same package. For explicit provider usage:
#
# from fastmcp.server.providers import FileSystemProvider
# provider = FileSystemProvider(
#     Path(__file__).parent / "mcp",
#     reload=settings.is_dev,
# )
# mcp = FastMCP(..., providers=[provider])
#
# For now we register tools manually in the mcp/ modules
# and import them here to trigger registration.

# Import tool modules to register with mcp
# (will be populated as tools are implemented)
import app.mcp.tools.admin
import app.mcp.tools.audio
import app.mcp.tools.crud
import app.mcp.tools.curation
import app.mcp.tools.delivery
import app.mcp.tools.discovery
import app.mcp.tools.reasoning
import app.mcp.tools.search
import app.mcp.tools.sets
import app.mcp.tools.sync
import app.mcp.tools.ym  # noqa: F401
