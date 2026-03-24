"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py             # production
"""

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
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
