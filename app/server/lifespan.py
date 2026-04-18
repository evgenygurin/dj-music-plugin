"""Composed server lifespan.

Uses the FastMCP v3 ``|`` composition operator. Keys yielded by each
@lifespan-decorated async generator are merged into the final context
dict made available to tools via ``ctx.fastmcp_context.state``.

Reserved keys (do NOT reuse across lifespans):
    db_engine, db_session_factory, provider_registry,
    analyzer_registry, audio_pipeline, transition_cache, session_store.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastmcp.server.lifespan import lifespan

from app.audio.analyzers import AnalyzerRegistry
from app.audio.pipeline import AnalysisPipeline
from app.config import get_settings
from app.db.session import get_engine, get_session_factory
from app.domain.optimization import GeneticAlgorithm, GreedyChainBuilder
from app.domain.transition.scorer import TransitionScorer
from app.providers.yandex.adapter import YandexAdapter
from app.providers.yandex.client import YandexClient
from app.providers.yandex.rate_limiter import TokenBucketRateLimiter
from app.registry.defaults import register_default_entities
from app.registry.entity import EntityRegistry
from app.registry.provider import ProviderRegistry
from app.server.session_store import InMemorySessionStore


def build_engine() -> Any:
    """Factory indirection — tests patch this symbol."""
    return get_engine()


def build_session_factory(engine: Any) -> Any:
    """Factory indirection — tests patch this symbol."""
    # ``get_session_factory`` is argumentless in v2.db.session; accept and
    # ignore ``engine`` so production and tests share one call shape.
    _ = engine
    return get_session_factory()


def build_yandex_adapter() -> YandexAdapter:
    """Build the default Yandex Music adapter. Tests patch this symbol."""
    settings = get_settings()
    client = YandexClient(
        token=settings.yandex.token,
        user_id=str(settings.yandex.user_id),
        base_url=settings.yandex.base_url,
        rate_limiter=TokenBucketRateLimiter(delay_s=settings.yandex.rate_limit_delay_s),
    )
    download_dir = Path(settings.yandex.library_path) if settings.yandex.library_path else None
    return YandexAdapter(client=client, download_dir=download_dir)


class TransitionCache:
    """In-memory LRU-ish placeholder — Phase 5 will replace with real impl."""

    def __init__(self, *, max_size: int, ttl_seconds: int) -> None:
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._data: dict[Any, Any] = {}

    def clear(self) -> None:
        self._data.clear()


@lifespan
async def db_lifespan(app: Any) -> AsyncIterator[dict[str, Any]]:
    """Open the SQLAlchemy async engine + session factory."""
    # Register entity schemas once per process (idempotent).
    if not EntityRegistry.names():
        register_default_entities()
    engine = build_engine()
    factory = build_session_factory(engine)
    try:
        yield {"db_engine": engine, "db_session_factory": factory}
    finally:
        dispose = getattr(engine, "dispose", None)
        if dispose is not None:
            with contextlib.suppress(Exception):
                await dispose()


@lifespan
async def provider_lifespan(app: Any) -> AsyncIterator[dict[str, Any]]:
    """Build and register music-platform providers; close on shutdown."""
    registry = ProviderRegistry()
    adapter = build_yandex_adapter()
    registry.register(adapter, default=True)
    try:
        yield {"provider_registry": registry}
    finally:
        await registry.close_all()


@lifespan
async def audio_lifespan(app: Any) -> AsyncIterator[dict[str, Any]]:
    """Initialize audio analyzers + pipeline (shared across tool calls)."""
    registry = AnalyzerRegistry()
    # Discovery issues should not break server startup — tools that need
    # specific analyzers will raise at call time.
    with contextlib.suppress(Exception):
        registry.discover()
    pipeline = AnalysisPipeline(registry)
    try:
        yield {"analyzer_registry": registry, "audio_pipeline": pipeline}
    finally:
        # Pipeline owns no resources that need explicit teardown today.
        pass


@lifespan
async def cache_lifespan(app: Any) -> AsyncIterator[dict[str, Any]]:
    """Process-wide transition score cache."""
    settings = get_settings()
    cache = TransitionCache(
        max_size=settings.transition.cache_max_size,
        ttl_seconds=settings.transition.cache_ttl_s,
    )
    try:
        yield {"transition_cache": cache}
    finally:
        cache.clear()


@lifespan
async def session_store_lifespan(app: Any) -> AsyncIterator[dict[str, Any]]:
    """Per-process in-memory session store (tool history, drafts, energy)."""
    store = InMemorySessionStore()
    try:
        yield {"session_store": store}
    finally:
        # Nothing to flush — data is per-process and lost on shutdown.
        pass


@lifespan
async def scoring_lifespan(app: Any) -> AsyncIterator[dict[str, Any]]:
    """Expose TransitionScorer + optimizer factory to compute tools."""
    scorer = TransitionScorer()

    def optimizer_builder(*, algorithm: str, scorer: TransitionScorer) -> Any:
        if algorithm == "greedy":
            return GreedyChainBuilder(scorer=scorer)
        return GeneticAlgorithm(scorer=scorer)

    yield {"transition_scorer": scorer, "optimizer": optimizer_builder}


def build_server_lifespan() -> Any:
    """Compose all lifespans in the canonical order.

    Order matters for teardown (reverse): cache/session close first,
    then audio, providers, db.
    """
    return (
        db_lifespan
        | provider_lifespan
        | audio_lifespan
        | cache_lifespan
        | session_store_lifespan
        | scoring_lifespan
    )
