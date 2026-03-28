"""FastMCP v3 server — DJ Music Plugin entry point.

Usage:
    uv run fastmcp dev app/server.py --reload   # development
    uv run fastmcp run app/server.py             # production

OpenTelemetry (optional, requires `uv sync --extra otel`):
    opentelemetry-instrument \
      --service_name dj-music \
      --exporter_otlp_endpoint http://localhost:4317 \
      fastmcp run app/server.py
"""

import logging
import os
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.providers import FileSystemProvider
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.cache import TransitionCache

# ── Observability Setup ──────────────────────────────

logger = logging.getLogger(__name__)

if settings.sentry_dsn:
    try:
        import sentry_sdk

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1 if not settings.debug else 1.0,
            environment="development" if settings.debug else "production",
        )
        logger.info("Sentry error tracking enabled")
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk not installed")

# ── Background Tasks Environment ─────────────────────

os.environ.setdefault("FASTMCP_DOCKET_URL", settings.docket_url)
os.environ.setdefault("FASTMCP_DOCKET_CONCURRENCY", str(settings.docket_concurrency))

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

    # Seed reference data (idempotent — skips if already populated)
    from app.core.seed import seed_reference_data

    await seed_reference_data(session_factory)

    try:
        yield {"db_engine": engine, "db_session_factory": session_factory}
    finally:
        await engine.dispose()


@lifespan
async def ym_lifespan(server):  # type: ignore[no-untyped-def]
    """Yandex Music client lifecycle with rate limiting."""
    from app.ym.client import YandexMusicClient
    from app.ym.rate_limiter import RateLimiter

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
    """Audio analyzer registry lifecycle."""
    from app.audio.analyzers import AnalyzerRegistry

    registry = AnalyzerRegistry()
    registry.discover()
    yield {"analyzer_registry": registry}


@lifespan
async def cache_lifespan(server):  # type: ignore[no-untyped-def]
    """Cache lifecycle — transition scores + storage backends."""
    transition_cache = TransitionCache(
        max_size=settings.transition_cache_max_size,
        ttl=settings.transition_cache_ttl,
    )
    try:
        yield {"transition_cache": transition_cache}
    finally:
        transition_cache.clear()


# ── Server ───────────────────────────────────────────

# Sampling handler for LLM-assisted tools.
#
# Two modes of operation:
#
# 1. CLIENT-DRIVEN (Claude Code MAX, no API key needed):
#    Claude Code is itself an LLM — it generates search queries, analysis, etc.
#    and passes results directly to tools via parameters (e.g. search_queries=[...]).
#    No sampling handler needed. Works with any Claude subscription.
#
# 2. SERVER-SIDE SAMPLING (requires DJ_ANTHROPIC_API_KEY):
#    ctx.sample() inside tools calls the Anthropic API via fallback handler.
#    Required for headless/automated scenarios without an LLM client.
#
# Note: Claude Code does NOT support MCP sampling (createMessage) as of 2026-03.
# See: https://github.com/anthropics/claude-code/issues/1785
# Therefore, sampling_handler_behavior="fallback" ensures the handler is used
# only when the client lacks sampling support (which includes Claude Code).

sampling_handler = None
if settings.anthropic_api_key:
    try:
        from anthropic import AsyncAnthropic
        from fastmcp.client.sampling.handlers.anthropic import (
            AnthropicSamplingHandler,
        )

        sampling_handler = AnthropicSamplingHandler(
            default_model=settings.sampling_model,
            client=AsyncAnthropic(api_key=settings.anthropic_api_key),
        )
        logger.info(
            "Sampling handler configured (Anthropic fallback, model=%s)",
            settings.sampling_model,
        )
    except ImportError:
        logger.warning("DJ_ANTHROPIC_API_KEY set but anthropic package not installed")
else:
    logger.info(
        "No DJ_ANTHROPIC_API_KEY configured. "
        "LLM-assisted tools use client-driven mode: Claude Code generates queries "
        "and passes them via tool parameters (e.g. search_queries=[...]). "
        "For server-side sampling, set DJ_ANTHROPIC_API_KEY."
    )

# FileSystemProvider auto-discovers @tool, @resource, @prompt decorated functions
# from all Python files in app/mcp/ — no manual imports needed.
mcp_dir = Path(__file__).parent / "mcp"

# ── Pre-constructor Transforms ───────────────────────
# BM25SearchTransform goes into the constructor via transforms= kwarg.
# ResourcesAsTools / PromptsAsTools need the mcp instance, so they are
# added post-construction to avoid circular dependency.
server_transforms = []
try:
    from fastmcp.server.transforms.search import BM25SearchTransform

    server_transforms.append(
        BM25SearchTransform(
            max_results=10,
            always_visible=["unlock_tools", "get_library_stats"],
            search_tool_name="search_tools",
            call_tool_name="run_tool",
        )
    )
except ImportError:
    logger.warning("BM25SearchTransform not available — install fastmcp[search]")

mcp = FastMCP(
    name=settings.server_name,
    instructions=(
        "DJ techno music library management, set building, "
        "and Yandex Music integration. "
        "Use unlock_tools to access hidden tool categories."
    ),
    providers=[FileSystemProvider(mcp_dir)],
    transforms=server_transforms,
    lifespan=db_lifespan | ym_lifespan | analyzer_lifespan | cache_lifespan,
    list_page_size=settings.pagination_size,
    on_duplicate="warn",
    mask_error_details=not settings.debug,  # hide stack traces in production
    sampling_handler=sampling_handler,
    sampling_handler_behavior="fallback" if sampling_handler else None,
)

# ── Post-constructor Transforms ──────────────────────
# These transforms require the mcp instance and cannot go into the constructor.
try:
    from fastmcp.server.transforms import PromptsAsTools, ResourcesAsTools

    mcp.add_transform(ResourcesAsTools(mcp))
    mcp.add_transform(PromptsAsTools(mcp))
except ImportError:
    pass

# ── Middleware Pipeline ──────────────────────────────
try:
    from app.mcp.middleware import (
        DetailedTimingMiddleware,
        StructuredLoggingMiddleware,
        YMRateLimitMiddleware,
    )

    mcp.add_middleware(
        StructuredLoggingMiddleware(
            include_payloads=settings.payload_logging,
            max_payload_length=500,
        )
    )
    mcp.add_middleware(DetailedTimingMiddleware())
    mcp.add_middleware(
        YMRateLimitMiddleware(
            delay_seconds=settings.ym_rate_limit_delay,
        )
    )
except ImportError:
    logger.warning("Custom middleware not available")

# Built-in FastMCP middleware
try:
    from fastmcp.server.middleware.error_handling import RetryMiddleware

    mcp.add_middleware(RetryMiddleware(max_retries=2))
except ImportError:
    pass

# ── Component Visibility ─────────────────────────────
# NOTE: audio tools are always visible (BUG-001 workaround).
# Claude Code doesn't re-fetch tools/list after ToolListChangedNotification,
# so mcp.disable() + unlock_tools() was ineffective. Audio tools are now
# always available. Atomic tools remain hidden (internal building blocks).
mcp.disable(tags={"atomic"})
