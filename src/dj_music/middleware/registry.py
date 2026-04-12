"""FastMCP middleware registration helpers."""

from __future__ import annotations

import logging
from typing import Any

from dj_music.core.config import settings


def register_middleware(
    mcp: Any,
    *,
    error_callback: Any = None,
    logger: logging.Logger | None = None,
) -> None:
    """Register custom and built-in middleware in stable order."""
    log = logger or logging.getLogger(__name__)

    try:
        from dj_music.middleware import (
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
        log.warning("Custom middleware not available")

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
