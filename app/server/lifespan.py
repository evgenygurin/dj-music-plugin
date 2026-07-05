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
from app.config.suno import SunoSettings
from app.db.session import get_engine, get_session_factory
from app.domain.optimization import ConstructiveSlotBuilder, GeneticAlgorithm, GreedyChainBuilder
from app.domain.transition.scorer import TransitionScorer
from app.providers.beatport.adapter import BeatportAdapter
from app.providers.beatport.client import BeatportClient
from app.providers.beatport.rate_limiter import TokenBucketRateLimiter as BeatportRateLimiter
from app.providers.suno.adapter import SunoAdapter
from app.providers.suno.client import SunoClient
from app.providers.suno.session_auth import SunoSessionCredentials
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


def build_beatport_adapter() -> BeatportAdapter | None:
    """Build the Beatport metadata adapter, or None if no credentials.

    Tests patch this symbol. Returns None when ``DJ_BEATPORT_USERNAME`` /
    ``DJ_BEATPORT_PASSWORD`` are unset so the registry simply omits the
    provider instead of registering a broken one.
    """
    bp = get_settings().beatport
    if not bp.enabled:
        return None
    client = BeatportClient(
        username=bp.username,
        password=bp.password,
        client_id=bp.client_id,
        redirect_uri=bp.redirect_uri,
        base_url=bp.base_url,
        rate_limiter=BeatportRateLimiter(delay_s=bp.rate_limit_delay_s),
        retry_attempts=bp.retry_attempts,
        timeout_s=bp.timeout_s,
    )
    return BeatportAdapter(
        client=client,
        bpm_tolerance=bp.match_bpm_tolerance,
        duration_tolerance_ms=bp.match_duration_tolerance_ms,
    )


def build_suno_adapter() -> SunoAdapter | None:
    """Build the Suno-compatible generation adapter, or None if disabled."""
    suno = SunoSettings()
    if not suno.enabled:
        return None
    session_auth = None
    if suno.use_session_auth:
        session_auth = SunoSessionCredentials(
            cookie_header=suno.cookie_header,
            client_token=suno.client_token,
            device_id=suno.device_id,
            bearer_token=suno.bearer_token,
            storage_state_path=Path(suno.storage_state_path),
        )
    client = SunoClient(
        api_key=suno.api_key,
        base_url=suno.effective_base_url,
        generate_path=suno.effective_generate_path,
        status_path=suno.effective_status_path,
        cancel_path=suno.effective_cancel_path,
        download_path=suno.download_path,
        captcha_check_path=suno.captcha_check_path,
        account_path=suno.effective_account_path,
        upload_base_url=suno.upload_base_url,
        auth_header=suno.auth_header,
        auth_scheme=suno.auth_scheme,
        session_auth=session_auth,
        clerk_url=suno.clerk_url,
        clerk_api_version=suno.clerk_api_version,
        clerk_js_version=suno.clerk_js_version,
        rate_limiter=TokenBucketRateLimiter(
            delay_s=suno.rate_limit_delay_s,
            max_retries=suno.retry_attempts,
        ),
        timeout_s=suno.timeout_s,
    )
    download_dir = Path(suno.download_dir) if suno.download_dir else None
    return SunoAdapter(
        client=client,
        default_model=suno.model,
        payload_mode=suno.effective_payload_mode,
        download_dir=download_dir,
        callback_url=suno.callback_url,
    )


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
    beatport = build_beatport_adapter()
    if beatport is not None:
        registry.register(beatport)
    suno = build_suno_adapter()
    if suno is not None:
        registry.register(suno)
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
        if algorithm == "constructive":
            return ConstructiveSlotBuilder(scorer=scorer)
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
