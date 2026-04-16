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
    """Register custom and built-in middleware in stable order."""
    log = logger or logging.getLogger(__name__)

    try:
        from app.controllers.middleware import (
            DetailedTimingMiddleware,
            StructuredLoggingMiddleware,
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
        mcp.add_middleware(
            StructuredLoggingMiddleware(
                include_payloads=settings.payload_logging,
                max_payload_length=500,
            )
        )
        mcp.add_middleware(DetailedTimingMiddleware())
    except ImportError:
        log.warning("Custom middleware not available")

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

    try:
        from app.controllers.middleware import YMRateLimitMiddleware

        mcp.add_middleware(
            YMRateLimitMiddleware(
                delay_seconds=settings.ym_rate_limit_delay,
            )
        )
    except ImportError:
        log.debug("YMRateLimitMiddleware unavailable")

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
        log.debug("Built-in FastMCP middleware unavailable")
