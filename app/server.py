"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development with hot reload
    uv run fastmcp run app/server.py             # production
"""

from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.providers import FileSystemProvider
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

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


# ── Provider ─────────────────────────────────────────

# FileSystemProvider scans app/mcp/ directory for tools/resources/prompts
# with standalone decorators (@tool, @resource, @prompt from fastmcp.*)
fs_provider = FileSystemProvider(
    Path(__file__).parent / "mcp",
    reload=settings.is_dev,  # hot reload in dev mode
)

# ── Server ───────────────────────────────────────────

mcp = FastMCP(
    name=settings.server_name,
    instructions=(
        "DJ techno music library management, set building, "
        "and Yandex Music integration. "
        "Use unlock_tools to access hidden tool categories."
    ),
    providers=[fs_provider],
    lifespan=db_lifespan,
    list_page_size=settings.pagination_size,
    on_duplicate="error",
)

# Hide audio tools at startup
mcp.disable(tags={"audio"})
