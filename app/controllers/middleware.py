"""FastMCP middleware: rate limiting, structured logging, timing, timeout.

All middleware inherit from fastmcp.server.middleware.Middleware.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from app.core.logging_config import mcp_extra

logger = logging.getLogger(__name__)


class ToolCallTimeoutMiddleware(Middleware):
    """Enforce per-tool execution timeouts on tools/call requests.

    FastMCP stores ``Tool.timeout`` as metadata but does not enforce it
    server-side. This middleware wraps ``on_call_tool`` with
    ``asyncio.wait_for`` so that long-running or blocking tool calls are
    cancelled and return a clean error to the client instead of starving
    the MCP stdio transport.

    Usage::

        middleware.add_middleware(
            ToolCallTimeoutMiddleware(
                tool_timeouts={"build_set": 120.0, "rebuild_set": 120.0},
                default_timeout=None,
            )
        )
    """

    def __init__(
        self,
        tool_timeouts: dict[str, float] | None = None,
        default_timeout: float | None = None,
    ) -> None:
        super().__init__()
        self._tool_timeouts: dict[str, float] = tool_timeouts or {}
        self._default_timeout = default_timeout

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        tool_name: str = context.message.name
        timeout = self._tool_timeouts.get(tool_name, self._default_timeout)
        if timeout is None:
            return await call_next(context)
        try:
            return await asyncio.wait_for(call_next(context), timeout=timeout)
        except TimeoutError:
            logger.error(
                "Tool %s exceeded timeout of %.1fs and was cancelled",
                tool_name,
                timeout,
            )
            raise


class YMRateLimitMiddleware(Middleware):
    """Rate limiting for platform API tool calls.

    Enforces minimum delay between consecutive platform tool calls
    to respect provider API rate limits (default 1.5s).
    """

    def __init__(self, delay_seconds: float = 1.5) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds
        self.last_call_time: float | None = None
        self._rate_limited_tools: frozenset[str] = frozenset(
            {
                "search_platform",
                "get_platform_tracks",
                "get_platform_artist_tracks",
                "get_platform_album",
                "platform_playlists",
                "platform_liked_tracks",
                "expand_platform_playlist",
                "push_set_to_platform",
            }
        )
        self._lock = asyncio.Lock()

    def _is_ym_tool(self, tool_name: str) -> bool:
        return tool_name in self._rate_limited_tools or tool_name.startswith("ym_")

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        tool_name = context.message.name

        if not self._is_ym_tool(tool_name):
            return await call_next(context)

        async with self._lock:
            now = time.monotonic()
            if self.last_call_time is not None:
                elapsed = now - self.last_call_time
                if elapsed < self.delay_seconds:
                    sleep_time = self.delay_seconds - elapsed
                    logger.debug(
                        "Platform rate limit: sleeping %.2fs before %s", sleep_time, tool_name
                    )
                    await asyncio.sleep(sleep_time)

            result = await call_next(context)
            self.last_call_time = time.monotonic()
            return result


class DjMcpRpcLoggingMiddleware(Middleware):
    """JSON-oriented MCP traffic logging (not FastMCP ``StructuredLoggingMiddleware``).

    Uses ``mcp_extra`` and :class:`~app.core.logging_config.JsonLogFormatter` for structured
    fields. Logs method, source, type, duration, optional payloads/errors.
    """

    def __init__(
        self,
        include_payloads: bool = False,
        max_payload_length: int = 500,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        super().__init__()
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length
        self._logger = logger_instance or logger

    def _truncate(self, data: Any) -> str:
        serialized = json.dumps(data, default=str)
        if len(serialized) > self.max_payload_length:
            return serialized[: self.max_payload_length] + "..."
        return serialized

    async def on_message(self, context: MiddlewareContext, call_next: Any) -> Any:
        start_time = time.monotonic()

        log_data: dict[str, Any] = {
            "kind": "message",
            "method": context.method,
            "source": context.source,
            "type": context.type,
        }

        if self.include_payloads:
            log_data["request"] = self._truncate(context.message)

        try:
            result = await call_next(context)
            log_data["duration_ms"] = round((time.monotonic() - start_time) * 1000, 2)
            if self.include_payloads and result is not None:
                log_data["response"] = self._truncate(result)
            self._logger.info("mcp.message", extra=mcp_extra(log_data))
            return result
        except Exception as e:
            log_data["duration_ms"] = round((time.monotonic() - start_time) * 1000, 2)
            log_data["error"] = {"type": type(e).__name__, "message": str(e)}
            self._logger.error("mcp.message.error", extra=mcp_extra(log_data))
            raise


class DetailedTimingMiddleware(Middleware):
    """Per-operation timing: tools, resources, prompts, overall requests."""

    def __init__(self, logger_instance: logging.Logger | None = None) -> None:
        super().__init__()
        self._logger = logger_instance or logger

    async def on_call_tool(self, context: MiddlewareContext, call_next: Any) -> Any:
        tool_name = context.message.name
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info(
                "mcp.timing.tool",
                extra=mcp_extra({"kind": "timing_tool", "name": tool_name, "duration_ms": ms}),
            )
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.warning(
                "mcp.timing.tool.error",
                extra=mcp_extra({"kind": "timing_tool", "name": tool_name, "duration_ms": ms}),
            )
            raise

    async def on_read_resource(self, context: MiddlewareContext, call_next: Any) -> Any:
        uri = context.message.uri
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info(
                "mcp.timing.resource",
                extra=mcp_extra({"kind": "timing_resource", "uri": str(uri), "duration_ms": ms}),
            )
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.warning(
                "mcp.timing.resource.error",
                extra=mcp_extra({"kind": "timing_resource", "uri": str(uri), "duration_ms": ms}),
            )
            raise

    async def on_get_prompt(self, context: MiddlewareContext, call_next: Any) -> Any:
        prompt_name = context.message.name
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info(
                "mcp.timing.prompt",
                extra=mcp_extra(
                    {"kind": "timing_prompt", "name": prompt_name, "duration_ms": ms},
                ),
            )
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.warning(
                "mcp.timing.prompt.error",
                extra=mcp_extra(
                    {"kind": "timing_prompt", "name": prompt_name, "duration_ms": ms},
                ),
            )
            raise

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info(
                "mcp.timing.request",
                extra=mcp_extra(
                    {"kind": "timing_request", "method": context.method, "duration_ms": ms},
                ),
            )
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info(
                "mcp.timing.request.error",
                extra=mcp_extra(
                    {"kind": "timing_request", "method": context.method, "duration_ms": ms},
                ),
            )
            raise
