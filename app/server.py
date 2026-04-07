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
from typing import Any

from fastmcp import FastMCP
from fastmcp.server.lifespan import lifespan
from fastmcp.server.providers import FileSystemProvider
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.core.cache import TransitionCache

# ── Observability Setup ──────────────────────────────

logger = logging.getLogger(__name__)

_sentry_enabled = False
if settings.sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment="development" if settings.debug else "production",
            release=f"dj-music@{os.environ.get('DJ_PLUGIN_VERSION', 'dev')}",
            traces_sample_rate=1.0 if settings.debug else 0.2,
            profiles_sample_rate=1.0 if settings.debug else 0.1,
            send_default_pii=False,
            attach_stacktrace=True,
            integrations=[
                AsyncioIntegration(),
                SqlalchemyIntegration(),
                # Capture WARNING+ as breadcrumbs, ERROR+ as events.
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
        )
        _sentry_enabled = True
        logger.info(
            "Sentry error tracking enabled (env=%s)", "debug" if settings.debug else "production"
        )
    except ImportError:
        logger.warning("SENTRY_DSN set but sentry-sdk not installed (uv sync --extra sentry)")


def _sentry_error_callback(error: Exception, ctx: Any) -> None:
    """Forward FastMCP middleware errors into Sentry with tool/method context."""
    if not _sentry_enabled:
        return
    try:
        import sentry_sdk

        method = getattr(ctx, "method", None) or "unknown"
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("mcp.method", method)
            scope.set_tag("mcp.error_type", type(error).__name__)
            sentry_sdk.capture_exception(error)
    except Exception as exc:  # never let telemetry crash the request path
        logger.debug("Sentry capture_exception failed: %s", exc)


# ── Background Tasks Environment ─────────────────────

os.environ.setdefault("FASTMCP_DOCKET_URL", settings.docket_url)
os.environ.setdefault("FASTMCP_DOCKET_CONCURRENCY", str(settings.docket_concurrency))

# ── Lifespans ────────────────────────────────────────


@lifespan
async def db_lifespan(server):  # type: ignore[no-untyped-def]
    """Database engine + session factory lifecycle."""
    connect_args = {}
    if settings.database_url.startswith("postgresql"):
        connect_args["statement_cache_size"] = 0  # required for PgBouncer/Supabase pooler
        connect_args["prepared_statement_cache_size"] = 0
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    # Seed reference data (idempotent — skips if already populated)
    from app.infrastructure.seed import seed_reference_data

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

    # NOTE: call_tool_name points at an internal stub that we immediately
    # disable below. Our own `run_tool` (app/mcp/tools/run_tool.py) takes
    # over — it accepts `arguments` as dict OR JSON string, which the
    # upstream proxy refuses.
    server_transforms.append(
        BM25SearchTransform(
            max_results=10,
            always_visible=["unlock_tools", "get_library_stats", "run_tool"],
            search_tool_name="search_tools",
            call_tool_name="_bm25_call_tool",
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
    from fastmcp.server.middleware.error_handling import (
        ErrorHandlingMiddleware,
        RetryMiddleware,
    )

    # ErrorHandlingMiddleware logs the full traceback to "fastmcp.errors" even
    # when mask_error_details=True hides details from the client. Without it,
    # production tool failures surface as opaque "Error calling tool 'X'" with
    # zero server-side context — which is exactly what made BUG-21 hard to
    # diagnose. Always include traceback regardless of debug mode: this stays
    # in the server log, never in the client response.
    mcp.add_middleware(
        ErrorHandlingMiddleware(
            include_traceback=True,
            transform_errors=True,
            error_callback=_sentry_error_callback if _sentry_enabled else None,
        )
    )
    mcp.add_middleware(RetryMiddleware(max_retries=2))
except ImportError:
    pass

# ── Component Visibility ─────────────────────────────
# NOTE: audio tools are always visible (BUG-001 workaround).
# Claude Code doesn't re-fetch tools/list after ToolListChangedNotification,
# so mcp.disable() + unlock_tools() was ineffective. Audio tools are now
# always available. Atomic tools remain hidden (internal building blocks).
mcp.disable(tags={"atomic"})

# Hide the upstream BM25 call_tool stub — our custom `run_tool`
# (app/mcp/tools/run_tool.py) replaces it with a version that accepts
# `arguments` as either a dict or a JSON string.
mcp.disable(names={"_bm25_call_tool"})
