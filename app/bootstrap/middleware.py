"""FastMCP middleware registration helpers."""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings


def register_middleware(
    mcp: Any,
    *,
    error_callback: Any = None,
    logger: logging.Logger | None = None,
) -> None:
    """Register middleware in FastMCP cookbook order.

    First ``add_middleware`` = outermost (runs first on the way in). Per fastmcp docs:
    error handling should wrap inner layers; request logging should be **last** added so it
    sits innermost and records the request/response after other middleware has run.
    """
    log = logger or logging.getLogger(__name__)
    mcp_request_log = logging.getLogger("app.mcp.request")

    # --- 1-2: errors + retries (outermost) ---
    try:
        from fastmcp.server.middleware.error_handling import (
            ErrorHandlingMiddleware,
            RetryMiddleware,
        )

        mcp.add_middleware(
            ErrorHandlingMiddleware(
                include_traceback=True,
                transform_errors=True,
                error_callback=error_callback,
            )
        )
        mcp.add_middleware(RetryMiddleware(max_retries=2))
    except ImportError:
        log.debug("Built-in ErrorHandling/Retry middleware unavailable")

    # --- 3-4: response size / cache (broad constraints) ---
    try:
        from fastmcp.server.middleware.response_limiting import ResponseLimitingMiddleware

        mcp.add_middleware(ResponseLimitingMiddleware(max_size=50_000))
    except ImportError:
        log.debug("ResponseLimitingMiddleware unavailable")

    try:
        from fastmcp.server.middleware.caching import ResponseCachingMiddleware

        mcp.add_middleware(
            ResponseCachingMiddleware(
                read_resource_settings={"enabled": False},
                call_tool_settings={"enabled": False},
            )
        )
    except ImportError:
        log.debug("ResponseCachingMiddleware unavailable")

    # --- 5: provider rate limit ---
    try:
        from app.controllers.middleware import YMRateLimitMiddleware

        mcp.add_middleware(
            YMRateLimitMiddleware(
                delay_seconds=settings.ym_rate_limit_delay,
            )
        )
    except ImportError:
        log.debug("YMRateLimitMiddleware unavailable")

    # --- 6-8: timeouts, timing, JSON request log (innermost) ---
    try:
        from app.controllers.middleware import (
            DetailedTimingMiddleware,
            DjMcpRpcLoggingMiddleware,
            ToolCallTimeoutMiddleware,
        )

        mcp.add_middleware(
            ToolCallTimeoutMiddleware(
                tool_timeouts={
                    "build_set": 120.0,
                    "rebuild_set": 120.0,
                    "score_transitions": 60.0,
                    "deliver_set": 300.0,
                    "analyze_track": 120.0,
                    "analyze_batch": 600.0,
                    "separate_stems": 300.0,
                },
            )
        )
        mcp.add_middleware(DetailedTimingMiddleware())
        mcp.add_middleware(
            DjMcpRpcLoggingMiddleware(
                include_payloads=settings.payload_logging,
                max_payload_length=500,
                logger_instance=mcp_request_log,
            )
        )
    except ImportError:
        log.warning("Custom DJ middleware not available")
