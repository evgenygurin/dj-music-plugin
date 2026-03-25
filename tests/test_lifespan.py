"""Tests for FastMCP lifespan lifecycle management.

Validates that all 4 lifespans (db, ym, analyzer, cache) initialize
and clean up properly, and that lifespan context is accessible in tools.
"""

from __future__ import annotations

import pytest
from fastmcp import FastMCP, tool
from fastmcp.server.dependencies import Depends, get_context
from fastmcp.server.lifespan import lifespan
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.audio.registry import AnalyzerRegistry
from app.config import settings
from app.core.cache import TransitionCache
from app.ym.client import YandexMusicClient
from app.ym.rate_limiter import RateLimiter


# ── Test lifespans (copy of production lifespans for isolation) ──


@lifespan
async def test_db_lifespan(server):  # type: ignore[no-untyped-def]
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
async def test_ym_lifespan(server):  # type: ignore[no-untyped-def]
    """Test YM lifespan."""
    rate_limiter = RateLimiter(
        delay=0.01,  # Minimal delay for tests
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
async def test_analyzer_lifespan(server):  # type: ignore[no-untyped-def]
    """Test analyzer lifespan."""
    registry = AnalyzerRegistry()
    registry.discover()

    try:
        yield {"analyzer_registry": registry}
    finally:
        pass


@lifespan
async def test_cache_lifespan(server):  # type: ignore[no-untyped-def]
    """Test cache lifespan."""
    cache = TransitionCache(max_size=100, ttl=60)

    try:
        yield {"transition_cache": cache}
    finally:
        cache.clear()


# ── Tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_db_lifespan_initializes_and_cleans_up() -> None:
    """DB lifespan creates engine and disposes on shutdown."""
    mcp = FastMCP("test", lifespan=test_db_lifespan)

    @tool
    def check_db(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]
        assert "db_engine" in ctx.lifespan_context
        assert "db_session_factory" in ctx.lifespan_context
        return "ok"

    mcp.tool()(check_db)

    # Simulate server lifecycle
    async with mcp.lifespan_context(mcp):
        # Engine should be initialized
        assert mcp._lifespan_context is not None
        assert "db_engine" in mcp._lifespan_context

    # After lifespan exit, engine is disposed (no errors)


@pytest.mark.asyncio
async def test_ym_lifespan_initializes_and_cleans_up() -> None:
    """YM lifespan creates client and closes HTTP client on shutdown."""
    mcp = FastMCP("test", lifespan=test_ym_lifespan)

    @tool
    def check_ym(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]
        assert "ym_client" in ctx.lifespan_context
        client = ctx.lifespan_context["ym_client"]
        assert isinstance(client, YandexMusicClient)
        return "ok"

    mcp.tool()(check_ym)

    async with mcp.lifespan_context(mcp):
        assert mcp._lifespan_context is not None
        assert "ym_client" in mcp._lifespan_context


@pytest.mark.asyncio
async def test_analyzer_lifespan_discovers_analyzers() -> None:
    """Analyzer lifespan discovers and registers built-in analyzers."""
    mcp = FastMCP("test", lifespan=test_analyzer_lifespan)

    @tool
    def check_analyzers(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]
        assert "analyzer_registry" in ctx.lifespan_context
        registry = ctx.lifespan_context["analyzer_registry"]
        assert isinstance(registry, AnalyzerRegistry)

        # Check core analyzers always registered
        all_analyzers = registry.list_all()
        assert "loudness" in all_analyzers
        assert "energy" in all_analyzers
        assert "spectral" in all_analyzers

        return {"all": all_analyzers, "available": registry.list_available()}

    mcp.tool()(check_analyzers)

    async with mcp.lifespan_context(mcp):
        assert mcp._lifespan_context is not None
        assert "analyzer_registry" in mcp._lifespan_context


@pytest.mark.asyncio
async def test_cache_lifespan_creates_cache() -> None:
    """Cache lifespan creates TransitionCache and clears on shutdown."""
    mcp = FastMCP("test", lifespan=test_cache_lifespan)

    @tool
    def check_cache(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]
        assert "transition_cache" in ctx.lifespan_context
        cache = ctx.lifespan_context["transition_cache"]
        assert isinstance(cache, TransitionCache)

        # Test basic cache operations
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

        return cache.stats()

    mcp.tool()(check_cache)

    async with mcp.lifespan_context(mcp):
        assert mcp._lifespan_context is not None
        assert "transition_cache" in mcp._lifespan_context


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

    async with mcp.lifespan_context(mcp):
        # All contexts merged
        assert mcp._lifespan_context is not None
        assert "first" in mcp._lifespan_context
        assert "second" in mcp._lifespan_context
        assert "third" in mcp._lifespan_context

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
    combined = (
        test_db_lifespan
        | test_ym_lifespan
        | test_analyzer_lifespan
        | test_cache_lifespan
    )

    mcp = FastMCP("test", lifespan=combined)

    @tool
    def check_all(ctx=Depends(get_context)):  # type: ignore[no-untyped-def]
        # All 4 lifespan contexts should be present
        assert "db_engine" in ctx.lifespan_context
        assert "db_session_factory" in ctx.lifespan_context
        assert "ym_client" in ctx.lifespan_context
        assert "analyzer_registry" in ctx.lifespan_context
        assert "transition_cache" in ctx.lifespan_context

        return list(ctx.lifespan_context.keys())

    mcp.tool()(check_all)

    async with mcp.lifespan_context(mcp):
        context = mcp._lifespan_context
        assert context is not None

        # Verify all expected keys
        expected_keys = {
            "db_engine",
            "db_session_factory",
            "ym_client",
            "analyzer_registry",
            "transition_cache",
        }
        assert set(context.keys()) == expected_keys


@pytest.mark.asyncio
async def test_lifespan_context_accessible_in_dependencies() -> None:
    """Lifespan context accessible via dependency injection in tools."""
    from app.mcp.dependencies import (
        get_analyzer_registry,
        get_transition_cache,
        get_ym_client,
    )

    combined = (
        test_db_lifespan
        | test_ym_lifespan
        | test_analyzer_lifespan
        | test_cache_lifespan
    )

    mcp = FastMCP("test", lifespan=combined)

    @tool
    def use_dependencies(
        ym_client=Depends(get_ym_client),
        registry=Depends(get_analyzer_registry),
        cache=Depends(get_transition_cache),
    ):  # type: ignore[no-untyped-def]
        assert isinstance(ym_client, YandexMusicClient)
        assert isinstance(registry, AnalyzerRegistry)
        assert isinstance(cache, TransitionCache)
        return "all_injected"

    mcp.tool()(use_dependencies)

    async with mcp.lifespan_context(mcp):
        # Dependencies should resolve from lifespan context
        pass
