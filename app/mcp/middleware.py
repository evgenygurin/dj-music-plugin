"""FastMCP middleware wrappers for custom middleware implementations.

This file contains thin wrappers around the actual middleware logic in custom_middleware.py.
The separation allows testing without importing the full FastMCP stack.
"""

from __future__ import annotations

from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.mcp.custom_middleware import (
    DetailedTimingMiddleware as _DetailedTimingMiddleware,
)
from app.mcp.custom_middleware import (
    StructuredLoggingMiddleware as _StructuredLoggingMiddleware,
)
from app.mcp.custom_middleware import (
    YMRateLimitMiddleware as _YMRateLimitMiddleware,
)


class YMRateLimitMiddleware(Middleware):
    """FastMCP wrapper for YM rate limiting middleware."""

    def __init__(self, delay_seconds: float = 1.5) -> None:
        super().__init__()
        self._impl = _YMRateLimitMiddleware(delay_seconds=delay_seconds)

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        return await self._impl.on_call_tool(context, call_next)


class StructuredLoggingMiddleware(Middleware):
    """FastMCP wrapper for structured logging middleware."""

    def __init__(
        self,
        include_payloads: bool = False,
        max_payload_length: int = 500,
        logger_instance: Any = None,
    ) -> None:
        super().__init__()
        self._impl = _StructuredLoggingMiddleware(
            include_payloads=include_payloads,
            max_payload_length=max_payload_length,
            logger_instance=logger_instance,
        )

    async def on_message(self, context: MiddlewareContext, call_next: Any) -> Any:
        return await self._impl.on_message(context, call_next)


class DetailedTimingMiddleware(Middleware):
    """FastMCP wrapper for detailed timing middleware."""

    def __init__(self, logger_instance: Any = None) -> None:
        super().__init__()
        self._impl = _DetailedTimingMiddleware(logger_instance=logger_instance)

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        return await self._impl.on_call_tool(context, call_next)

    async def on_read_resource(self, context: MiddlewareContext, call_next: Any) -> Any:
        return await self._impl.on_read_resource(context, call_next)

    async def on_get_prompt(self, context: MiddlewareContext, call_next: Any) -> Any:
        return await self._impl.on_get_prompt(context, call_next)

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        return await self._impl.on_request(context, call_next)
