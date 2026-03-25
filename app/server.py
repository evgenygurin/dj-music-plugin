"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py             # production
"""

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.middleware import PingMiddleware
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from fastmcp.server.middleware.response_limiting import (
    ResponseLimitingMiddleware,
)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.mcp.middleware import (
    DetailedTimingMiddleware,
    StructuredLoggingMiddleware,
    YMRateLimitMiddleware,
)

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
# Order matters: first added runs first on the way in, last on the way out.
# See design spec §2.5 for rationale.

# 1. Error handling (outermost — catches all downstream errors)
mcp.add_middleware(
    ErrorHandlingMiddleware(
        include_traceback=settings.debug,
        transform_errors=True,
    )
)

# 2. Structured logging (log everything after error handling)
mcp.add_middleware(
    StructuredLoggingMiddleware(
        include_payloads=settings.payload_logging,
        max_payload_length=500,
    )
)

# 3. Detailed timing (per-operation timing)
mcp.add_middleware(DetailedTimingMiddleware())

# 4. Global rate limiting (10 req/s, burst 20)
mcp.add_middleware(
    RateLimitingMiddleware(
        max_requests_per_second=10.0,
        burst_capacity=20,
    )
)

# 5. Response limiting (max 50KB responses)
mcp.add_middleware(
    ResponseLimitingMiddleware(
        max_size=50_000,  # 50KB
        truncation_suffix="\n\n[Response truncated due to size limit]",
    )
)

# 6. Ping middleware (30s keep-alive for long-lived connections)
mcp.add_middleware(PingMiddleware(interval_ms=30_000))

# 7. YM-specific rate limiting (1.5s between YM tool calls)
mcp.add_middleware(YMRateLimitMiddleware(delay_seconds=settings.ym_rate_limit_delay))

# Hide audio tools at startup
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
