"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py             # production
"""

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audio.registry import AnalyzerRegistry
from app.config import settings
from app.core.cache import TransitionCache
from app.ym.client import YandexMusicClient
from app.ym.rate_limiter import RateLimiter

# ── Lifespans ────────────────────────────────────────


@lifespan
async def db_lifespan(server):  # type: ignore[no-untyped-def]
    """Database engine + session factory lifecycle.

    Creates async SQLAlchemy engine and session factory.
    Yields context accessible via ctx.lifespan_context["db_*"].
    Ensures proper engine disposal on shutdown.
    """
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
async def ym_lifespan(server):  # type: ignore[no-untyped-def]
    """Yandex Music client lifecycle.

    Creates YM client with rate limiting (token bucket + exponential backoff).
    Yields context accessible via ctx.lifespan_context["ym_client"].
    Ensures proper HTTP client cleanup on shutdown.
    """
    rate_limiter = RateLimiter(
        delay=settings.ym_rate_limit_delay,
        max_retries=settings.ym_retry_attempts,
        backoff_factor=settings.ym_retry_backoff_factor,
    )

    client = YandexMusicClient(
        token=settings.ym_token,
        user_id=settings.ym_user_id,
        base_url=settings.ym_base_url,
        rate_limiter=rate_limiter,
    )

    try:
        yield {"ym_client": client}
    finally:
        await client.close()


@lifespan
async def analyzer_lifespan(server):  # type: ignore[no-untyped-def]
    """Audio analyzer registry lifecycle.

    Discovers and registers all available audio analyzers.
    Core analyzers (loudness, energy, spectral) always available.
    Optional analyzers (BPM, key, MFCC) require [audio] extra.
    Yields context accessible via ctx.lifespan_context["analyzer_registry"].
    """
    registry = AnalyzerRegistry()
    registry.discover()  # Auto-discover built-in analyzers

    try:
        yield {"analyzer_registry": registry}
    finally:
        # No cleanup needed — registry is stateless
        pass


@lifespan
async def cache_lifespan(server):  # type: ignore[no-untyped-def]
    """Transition score cache lifecycle.

    Creates in-memory LRU cache for expensive transition scores.
    Yields context accessible via ctx.lifespan_context["transition_cache"].
    Cache is cleared on shutdown.
    """
    cache = TransitionCache(
        max_size=settings.transition_cache_max_size,
        ttl=settings.transition_cache_ttl,
    )

    try:
        yield {"transition_cache": cache}
    finally:
        cache.clear()


# ── Server ───────────────────────────────────────────

# Compose lifespans with | operator (enter left-to-right, exit right-to-left)
mcp = FastMCP(
    name=settings.server_name,
    instructions=(
        "DJ techno music library management, set building, "
        "and Yandex Music integration. "
        "Use unlock_tools to access hidden tool categories."
    ),
    lifespan=db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan,
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
