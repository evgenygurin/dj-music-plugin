"""Custom middleware implementations that can be used with FastMCP.

These middleware are designed to work with fastmcp.server.middleware.Middleware
but are defined here to avoid circular import issues during testing.

Import these in server.py like:
    from app.mcp.custom_middleware import (
        YMRateLimitMiddleware,
        StructuredLoggingMiddleware,
        DetailedTimingMiddleware,
    )

Then wrap them in actual FastMCP Middleware classes in server.py.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class YMRateLimitMiddleware:
    """Rate limiting specifically for Yandex Music API tool calls.

    Enforces settings.ym_rate_limit_delay between consecutive YM tool calls
    to respect YM API rate limits (default 1.5s).
    """

    def __init__(self, delay_seconds: float = 1.5) -> None:
        """Initialize YM rate limiter.

        Args:
            delay_seconds: Minimum seconds between YM tool calls
        """
        self.delay_seconds = delay_seconds
        self.last_call_time: float | None = None
        self._ym_tool_prefix = "ym_"

    def _is_ym_tool(self, tool_name: str) -> bool:
        """Check if tool is a Yandex Music tool."""
        return tool_name.startswith(self._ym_tool_prefix)

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        """Rate limit YM tool calls."""
        tool_name = context.message.name

        if not self._is_ym_tool(tool_name):
            # Not a YM tool, proceed immediately
            return await call_next(context)

        # YM tool - enforce rate limit
        now = time.monotonic()

        if self.last_call_time is not None:
            elapsed = now - self.last_call_time
            if elapsed < self.delay_seconds:
                sleep_time = self.delay_seconds - elapsed
                logger.debug(
                    "YM rate limit: sleeping %.2fs before %s",
                    sleep_time,
                    tool_name,
                )
                await asyncio.sleep(sleep_time)

        result = await call_next(context)
        self.last_call_time = time.monotonic()

        return result


class StructuredLoggingMiddleware:
    """JSON-formatted logging for all MCP requests and responses.

    Logs include:
    - timestamp (ISO 8601)
    - method
    - source (client/server)
    - type (request/notification)
    - duration_ms (on response)
    - error (if any)
    - payload (if enabled)
    """

    def __init__(
        self,
        include_payloads: bool = False,
        max_payload_length: int = 500,
        logger_instance: logging.Logger | None = None,
    ) -> None:
        """Initialize structured logging middleware.

        Args:
            include_payloads: Log request/response content
            max_payload_length: Truncate payloads beyond this length
            logger_instance: Custom logger (default: module logger)
        """
        self.include_payloads = include_payloads
        self.max_payload_length = max_payload_length
        self.logger = logger_instance or logger

    def _truncate(self, data: Any) -> str:
        """Serialize and truncate data for logging."""
        serialized = json.dumps(data, default=str)
        if len(serialized) > self.max_payload_length:
            return serialized[: self.max_payload_length] + "..."
        return serialized

    async def on_message(self, context: Any, call_next: Any) -> Any:
        """Log all messages with structured JSON."""
        start_time = time.monotonic()

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
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

            self.logger.info(json.dumps(log_data))
            return result

        except Exception as e:
            log_data["duration_ms"] = round((time.monotonic() - start_time) * 1000, 2)
            log_data["error"] = {
                "type": type(e).__name__,
                "message": str(e),
            }
            self.logger.error(json.dumps(log_data))
            raise


class DetailedTimingMiddleware:
    """Per-operation timing with separate tracking for tools, resources, prompts.

    Logs:
    - Overall request duration
    - Per-tool timing (tool name + duration)
    - Per-resource timing (resource URI + duration)
    - Per-prompt timing (prompt name + duration)
    """

    def __init__(self, logger_instance: logging.Logger | None = None) -> None:
        """Initialize timing middleware.

        Args:
            logger_instance: Custom logger (default: module logger)
        """
        self.logger = logger_instance or logger

    async def on_call_tool(self, context: Any, call_next: Any) -> Any:
        """Time tool execution."""
        tool_name = context.message.name
        start_time = time.monotonic()

        try:
            result = await call_next(context)
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.info("Tool timing: %s completed in %.2fms", tool_name, duration_ms)
            return result
        except Exception:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.warning("Tool timing: %s failed after %.2fms", tool_name, duration_ms)
            raise

    async def on_read_resource(self, context: Any, call_next: Any) -> Any:
        """Time resource reads."""
        uri = context.message.uri
        start_time = time.monotonic()

        try:
            result = await call_next(context)
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.info("Resource timing: %s read in %.2fms", uri, duration_ms)
            return result
        except Exception:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.warning("Resource timing: %s failed after %.2fms", uri, duration_ms)
            raise

    async def on_get_prompt(self, context: Any, call_next: Any) -> Any:
        """Time prompt retrieval."""
        prompt_name = context.message.name
        start_time = time.monotonic()

        try:
            result = await call_next(context)
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.info(
                "Prompt timing: %s retrieved in %.2fms",
                prompt_name,
                duration_ms,
            )
            return result
        except Exception:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.warning(
                "Prompt timing: %s failed after %.2fms",
                prompt_name,
                duration_ms,
            )
            raise

    async def on_request(self, context: Any, call_next: Any) -> Any:
        """Time overall request."""
        start_time = time.monotonic()

        try:
            result = await call_next(context)
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.debug(
                "Request timing: %s completed in %.2fms",
                context.method,
                duration_ms,
            )
            return result
        except Exception:
            duration_ms = round((time.monotonic() - start_time) * 1000, 2)
            self.logger.debug(
                "Request timing: %s failed after %.2fms",
                context.method,
                duration_ms,
            )
            raise
