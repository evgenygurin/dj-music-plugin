"""Tests for FastMCP lifespan lifecycle management.

Validates that all 4 lifespans (db, ym, analyzer, cache) initialize
and clean up properly, and that lifespan context is accessible in tools.
"""

from __future__ import annotations

import pytest
from fastmcp import Client, FastMCP
from fastmcp.dependencies import Depends
from fastmcp.server.dependencies import get_context
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audio.registry import AnalyzerRegistry
from app.core.cache import TransitionCache
from app.ym.client import YandexMusicClient
from app.ym.rate_limiter import RateLimiter

# ── Test lifespans (copy of production lifespans for isolation) ──
# Prefix with _ to prevent pytest collection warnings


@lifespan
async def _db_lifespan(server):  # type: ignore[no-untyped-def]
    """Test DB lifespan."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        pool_pre_ping=True,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield {"db_engine": engine, "db_session_factory": session_factory}
    finally:
        await engine.dispose()


@lifespan
async def _ym_lifespan(server):  # type: ignore[no-untyped-def]
    """Test YM lifespan."""
    rate_limiter = RateLimiter(
        delay=0.01,
        max_retries=1,
        backoff_factor=1.5,
    )
    client = YandexMusicClient(
        token="test_token",
        user_id="test_user",
        base_url="https://api.music.yandex.net",
        rate_limiter=rate_limiter,
    )
    try:
        yield {"ym_client": client}
    finally:
        await client.close()


@lifespan
async def _analyzer_lifespan(server):  # type: ignore[no-untyped-def]
    """Test analyzer lifespan."""
    registry = AnalyzerRegistry()
    registry.discover()
    try:
        yield {"analyzer_registry": registry}
    finally:
        pass


@lifespan
async def _cache_lifespan(server):  # type: ignore[no-untyped-def]
    """Test cache lifespan."""
    cache = TransitionCache(max_size=100, ttl=60)
    try:
        yield {"transition_cache": cache}
    finally:
        cache.clear()


# ── Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_db_lifespan_via_tool() -> None:
    """DB lifespan provides engine and session_factory to tools."""
    mcp = FastMCP("test", lifespan=_db_lifespan)

    @mcp.tool()
    def check_db(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]  # noqa: B008
        assert "db_engine" in ctx.lifespan_context
        assert "db_session_factory" in ctx.lifespan_context
        return "ok"

    async with Client(mcp) as client:
        result = await client.call_tool("check_db")
        assert result.content[0].text == "ok"


@pytest.mark.asyncio
async def test_ym_lifespan_via_tool() -> None:
    """YM lifespan provides client instance to tools."""
    mcp = FastMCP("test", lifespan=_ym_lifespan)

    @mcp.tool()
    def check_ym(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]  # noqa: B008
        client = ctx.lifespan_context["ym_client"]
        assert isinstance(client, YandexMusicClient)
        return "ok"

    async with Client(mcp) as client:
        result = await client.call_tool("check_ym")
        assert result.content[0].text == "ok"


@pytest.mark.asyncio
async def test_analyzer_lifespan_discovers_analyzers() -> None:
    """Analyzer lifespan discovers and registers built-in analyzers."""
    mcp = FastMCP("test", lifespan=_analyzer_lifespan)

    @mcp.tool()
    def check_analyzers(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]  # noqa: B008
        registry = ctx.lifespan_context["analyzer_registry"]
        assert isinstance(registry, AnalyzerRegistry)
        all_analyzers = registry.list_all()
        assert "loudness" in all_analyzers
        assert "energy" in all_analyzers
        assert "spectral" in all_analyzers
        return "ok"

    async with Client(mcp) as client:
        result = await client.call_tool("check_analyzers")
        assert result.content[0].text == "ok"


@pytest.mark.asyncio
async def test_cache_lifespan_creates_cache() -> None:
    """Cache lifespan creates TransitionCache with basic operations."""
    mcp = FastMCP("test", lifespan=_cache_lifespan)

    @mcp.tool()
    def check_cache(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]  # noqa: B008
        cache = ctx.lifespan_context["transition_cache"]
        assert isinstance(cache, TransitionCache)
        cache.put(
            1,
            2,
            bpm_score=0.9,
            harmonic_score=0.8,
            energy_score=0.85,
            spectral_score=0.7,
            groove_score=0.75,
            overall_score=0.8,
        )
        score = cache.get(1, 2)
        assert score is not None
        assert score.overall_score == 0.8
        return "ok"

    async with Client(mcp) as client:
        result = await client.call_tool("check_cache")
        assert result.content[0].text == "ok"


@pytest.mark.asyncio
async def test_composed_lifespans_enter_in_order_exit_in_reverse() -> None:
    """Composed lifespans with | operator enter left-to-right, exit right-to-left."""
    order: list[str] = []

    @lifespan
    async def first(server):  # type: ignore[no-untyped-def]
        order.append("first_enter")
        try:
            yield {"first": True}
        finally:
            order.append("first_exit")

    @lifespan
    async def second(server):  # type: ignore[no-untyped-def]
        order.append("second_enter")
        try:
            yield {"second": True}
        finally:
            order.append("second_exit")

    @lifespan
    async def third(server):  # type: ignore[no-untyped-def]
        order.append("third_enter")
        try:
            yield {"third": True}
        finally:
            order.append("third_exit")

    mcp = FastMCP("test", lifespan=first | second | third)

    @mcp.tool()
    def check_all(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]  # noqa: B008
        assert "first" in ctx.lifespan_context
        assert "second" in ctx.lifespan_context
        assert "third" in ctx.lifespan_context
        return "ok"

    async with Client(mcp) as client:
        result = await client.call_tool("check_all")
        assert result.content[0].text == "ok"

    # Verify LIFO order: enter left-to-right, exit right-to-left
    assert order == [
        "first_enter",
        "second_enter",
        "third_enter",
        "third_exit",
        "second_exit",
        "first_exit",
    ]


@pytest.mark.asyncio
async def test_all_four_lifespans_compose_correctly() -> None:
    """All 4 production lifespans compose and provide context."""
    combined = _db_lifespan | _ym_lifespan | _analyzer_lifespan | _cache_lifespan
    mcp = FastMCP("test", lifespan=combined)

    @mcp.tool()
    def check_all(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]  # noqa: B008
        expected_keys = {
            "db_engine",
            "db_session_factory",
            "ym_client",
            "analyzer_registry",
            "transition_cache",
        }
        assert set(ctx.lifespan_context.keys()) == expected_keys
        return "ok"

    async with Client(mcp) as client:
        result = await client.call_tool("check_all")
        assert result.content[0].text == "ok"
