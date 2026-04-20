"""Middleware pipeline — 15 classes after PR1 (14 after PR2 drops ToolCallTimeout).

Order is outermost→innermost; the first added wraps all others at call time.
Do not reorder without updating blueprint §11 and ``tests/server/test_ordering.py``.

Five middleware classes below are imported from ``fastmcp.server.middleware.*``:
``DetailedTimingMiddleware``, ``RetryMiddleware``, ``ResponseLimitingMiddleware``,
``ResponseCachingMiddleware``, ``StructuredLoggingMiddleware``. FastMCP v3 ships
these with the same semantics our hand-rolled versions had; the core test suite
covers their behaviour.

``DomainErrorMiddleware`` (formerly ``ErrorHandlingMiddleware``) is ours — it
maps domain exceptions to ``ToolError`` and is distinct from FastMCP's built-in
``ErrorHandlingMiddleware`` (which focuses on exception logging/tracebacks).

``OTELTracingMiddleware`` was removed: FastMCP v3 ships native OTEL instrumentation
with MCP semantic conventions. ``ToolCallTimeoutMiddleware`` will be removed in
PR2 and per-tool timeouts set via ``@tool(timeout=N)``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastmcp.server.middleware.caching import (
    CallToolSettings,
    ListPromptsSettings,
    ListResourcesSettings,
    ListToolsSettings,
    ReadResourceSettings,
    ResponseCachingMiddleware,
)
from fastmcp.server.middleware.error_handling import RetryMiddleware
from fastmcp.server.middleware.logging import StructuredLoggingMiddleware
from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware
from fastmcp.server.middleware.timing import DetailedTimingMiddleware
from key_value.aio.stores.memory import MemoryStore

from app.server.middleware.audit_log import AuditLogMiddleware
from app.server.middleware.cost_tracking import CostTrackingMiddleware
from app.server.middleware.db_session import DbSessionMiddleware
from app.server.middleware.deprecation_warning import DeprecationWarningMiddleware
from app.server.middleware.domain_error import DomainErrorMiddleware
from app.server.middleware.progress_throttle import ProgressThrottleMiddleware
from app.server.middleware.provider_rate_limit import ProviderRateLimitMiddleware
from app.server.middleware.sampling_budget import SamplingBudgetMiddleware
from app.server.middleware.sentry_context import SentryContextMiddleware
from app.server.middleware.tool_timeout import ToolCallTimeoutMiddleware
from app.shared.errors import TransientError

if TYPE_CHECKING:
    from fastmcp.server.middleware import Middleware

    from app.config import Settings


# Tools whose outputs can be safely cached by name + args. Must match
# ``readOnlyHint=True`` annotations on the actual ``@tool`` declarations in
# ``app/tools/``. Passed to the built-in ``ResponseCachingMiddleware`` as
# ``CallToolSettings.included_tools`` so mutating tools are never cached.
_READ_ONLY_TOOLS: tuple[str, ...] = (
    "entity_list",
    "entity_get",
    "entity_aggregate",
    "provider_read",
    "provider_search",
    "transition_score_pool",
    # ``sequence_optimize`` carries ``readOnlyHint=True`` (it reads features and
    # pair scores, no DB writes); cacheable in the v0 pipeline. Keep parity.
    "sequence_optimize",
    # UI tools from PR #113 — all readOnlyHint=True, render Prefab dashboards.
    "ui_library_audit",
    "ui_library_dashboard",
    "ui_camelot_wheel",
    "ui_score_pool_matrix",
    "ui_set_view",
    "ui_transition_score",
)


def build_middleware_list(settings: Settings) -> list[Middleware]:
    """Construct the 15-middleware pipeline in canonical order (outer→inner)."""
    return [
        # 1 outermost — domain-error → ToolError translation
        DomainErrorMiddleware(mask_details=not settings.mcp.debug),
        # 2 — sentry breadcrumb context
        SentryContextMiddleware(),
        # (OTELTracingMiddleware removed — FastMCP v3 native tracing)
        # 3 — per-tool/resource/prompt timing (built-in)
        DetailedTimingMiddleware(),
        # 4 — audit-log of mutations
        AuditLogMiddleware(),
        # 5 — retry transient errors (built-in). Preserve the 0.5s base delay
        # our removed ``app/server/middleware/retry.py`` used. FastMCP's default
        # ``base_delay=1.0`` would double the wait at every retry step and push
        # timeout-sensitive tool calls over their deadline.
        RetryMiddleware(
            max_retries=settings.mcp.retry_max_attempts,
            base_delay=settings.mcp.retry_base_delay_s,
            retry_exceptions=(TransientError,),
        ),
        # 6 — cap response size (built-in)
        ResponseLimitingMiddleware(max_size=settings.mcp.response_max_bytes),
        # 7 — cache read-only tool calls (built-in, explicit opt-in per tool).
        # Bounded in-memory storage preserves the ``response_cache_max``
        # entry-count guardrail our custom middleware used to provide; without
        # it, high-cardinality tool args can grow the cache unboundedly. For
        # distributed deployments, swap ``cache_storage`` for Redis/FileTree.
        ResponseCachingMiddleware(
            cache_storage=MemoryStore(
                max_entries_per_collection=settings.mcp.response_cache_max,
            ),
            call_tool_settings=CallToolSettings(
                ttl=settings.mcp.response_cache_ttl,
                included_tools=list(_READ_ONLY_TOOLS),
            ),
            list_tools_settings=ListToolsSettings(enabled=False),
            list_resources_settings=ListResourcesSettings(enabled=False),
            list_prompts_settings=ListPromptsSettings(enabled=False),
            read_resource_settings=ReadResourceSettings(enabled=False),
        ),
        # 8 — warn on deprecated tool version calls
        DeprecationWarningMiddleware(),
        # 9 — provider/LLM cost accounting
        CostTrackingMiddleware(),
        # 10 — LLM sampling budget per session
        SamplingBudgetMiddleware(),
        # 11 — throttle progress events to 1/sec
        ProgressThrottleMiddleware(),
        # 12 — per-tool timeout (removed in PR2 — @tool(timeout=N))
        ToolCallTimeoutMiddleware(),
        # 13 — Yandex Music rate limit
        ProviderRateLimitMiddleware(),
        # 14 — open UoW, commit/rollback
        DbSessionMiddleware(),
        # 15 innermost — structured log at tool boundary (built-in)
        StructuredLoggingMiddleware(include_payloads=False),
    ]


# Legacy tuple — the classes in order, for the ordering test in
# ``tests/server/test_ordering.py``. Instances are built via
# ``build_middleware_list(settings)``; this tuple carries only types.
ALL_MIDDLEWARE: tuple[type, ...] = (
    DomainErrorMiddleware,
    SentryContextMiddleware,
    DetailedTimingMiddleware,
    AuditLogMiddleware,
    RetryMiddleware,
    ResponseLimitingMiddleware,
    ResponseCachingMiddleware,
    DeprecationWarningMiddleware,
    CostTrackingMiddleware,
    SamplingBudgetMiddleware,
    ProgressThrottleMiddleware,
    ToolCallTimeoutMiddleware,
    ProviderRateLimitMiddleware,
    DbSessionMiddleware,
    StructuredLoggingMiddleware,
)

__all__ = ["ALL_MIDDLEWARE", "_READ_ONLY_TOOLS", "build_middleware_list"]
