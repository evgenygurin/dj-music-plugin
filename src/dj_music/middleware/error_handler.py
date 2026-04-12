"""FastMCP middleware: rate limiting, structured logging, timing.

All middleware inherit from fastmcp.server.middleware.Middleware.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastmcp.server.middleware import Middleware, MiddlewareContext

from dj_music.core.utils.time import utc_timestamp_iso

logger = logging.getLogger(__name__)


class YMRateLimitMiddleware(Middleware):
    """Rate limiting for Yandex Music API tool calls.

    Enforces minimum delay between consecutive YM tool calls
    to respect YM API rate limits (default 1.5s).
    """

    def __init__(self, delay_seconds: float = 1.5) -> None:
        super().__init__()
        self.delay_seconds = delay_seconds
        self.last_call_time: float | None = None
        self._ym_tool_prefix = "ym_"
        self._lock = asyncio.Lock()

    def _is_ym_tool(self, tool_name: str) -> bool:
        return tool_name.startswith(self._ym_tool_prefix)

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
                    logger.debug("YM rate limit: sleeping %.2fs before %s", sleep_time, tool_name)
                    await asyncio.sleep(sleep_time)

            result = await call_next(context)
            self.last_call_time = time.monotonic()
            return result


class StructuredLoggingMiddleware(Middleware):
    """JSON-formatted logging for all MCP messages.

    Logs: timestamp, method, source, type, duration_ms, error, payload (optional).
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
            "timestamp": utc_timestamp_iso(),
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
            self._logger.info(json.dumps(log_data))
            return result
        except Exception as e:
            log_data["duration_ms"] = round((time.monotonic() - start_time) * 1000, 2)
            log_data["error"] = {"type": type(e).__name__, "message": str(e)}
            self._logger.error(json.dumps(log_data))
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
            self._logger.info("Tool timing: %s completed in %.2fms", tool_name, ms)
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.warning("Tool timing: %s failed after %.2fms", tool_name, ms)
            raise

    async def on_read_resource(self, context: MiddlewareContext, call_next: Any) -> Any:
        uri = context.message.uri
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info("Resource timing: %s read in %.2fms", uri, ms)
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.warning("Resource timing: %s failed after %.2fms", uri, ms)
            raise

    async def on_get_prompt(self, context: MiddlewareContext, call_next: Any) -> Any:
        prompt_name = context.message.name
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.info("Prompt timing: %s retrieved in %.2fms", prompt_name, ms)
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.warning("Prompt timing: %s failed after %.2fms", prompt_name, ms)
            raise

    async def on_request(self, context: MiddlewareContext, call_next: Any) -> Any:
        start_time = time.monotonic()
        try:
            result = await call_next(context)
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.debug("Request timing: %s completed in %.2fms", context.method, ms)
            return result
        except Exception:
            ms = round((time.monotonic() - start_time) * 1000, 2)
            self._logger.debug("Request timing: %s failed after %.2fms", context.method, ms)
            raise
