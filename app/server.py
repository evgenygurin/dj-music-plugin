"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py             # production
"""

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.storage import create_storage_backend, create_transition_cache_backend

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


@lifespan
async def cache_lifespan(server):  # type: ignore[no-untyped-def]
    """Storage backends for caching (response cache + transition scores)."""
    response_cache_store = create_storage_backend()
    transition_cache_store = create_transition_cache_backend()
    try:
        yield {
            "response_cache_store": response_cache_store,
            "transition_cache_store": transition_cache_store,
        }
    finally:
        # Cleanup if needed (Redis connections close automatically)
        pass


# ── Server ───────────────────────────────────────────

mcp = FastMCP(
    name=settings.server_name,
    instructions=(
        "DJ techno music library management, set building, "
        "and Yandex Music integration. "
        "Use unlock_tools to access hidden tool categories."
    ),
    lifespan=db_lifespan | cache_lifespan,  # Compose lifespans
    list_page_size=settings.pagination_size,
    on_duplicate="error",
)

# ── Middleware ───────────────────────────────────────

# Response caching for read-only tools (if enabled)
if settings.response_cache_enabled:
    from fastmcp.server.middleware.caching import CallToolSettings

    # Access response_cache_store from lifespan context after server init
    # For now, create inline — will be refactored when middleware supports lazy init
    response_cache_store = create_storage_backend()
    mcp.add_middleware(
        ResponseCachingMiddleware(
            cache_storage=response_cache_store,
            call_tool_settings=CallToolSettings(
                enabled=True,
                ttl=settings.response_cache_ttl,
            ),
        )
    )

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
