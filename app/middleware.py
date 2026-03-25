"""Custom middleware for FastMCP server.

Provides timing, logging, and observability middleware that integrates with OpenTelemetry.
"""

import logging
import time
from typing import Any

from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
from opentelemetry import trace

from app.config import settings

logger = logging.getLogger(__name__)


class DetailedTimingMiddleware(Middleware):
    """Records detailed execution timing for each MCP message.

    Timing data is:
    1. Logged at INFO level (if debug mode)
    2. Added as OTEL span attributes (if tracing enabled)
    3. Included in response meta when applicable
    """

    async def on_message(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """Measure message execution time and record in multiple places."""
        start_time = time.perf_counter()
        method = context.method

        try:
            result = await call_next(context)
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Record in OTEL span
            span = trace.get_current_span()
            if span.is_recording():
                span.set_attribute("dj.timing.duration_ms", elapsed_ms)
                span.set_attribute("dj.timing.success", True)
                span.set_attribute("dj.timing.method", method)

            # Log in debug mode
            if settings.debug:
                logger.info(
                    "MCP operation timing",
                    extra={
                        "method": method,
                        "duration_ms": f"{elapsed_ms:.2f}",
                        "success": True,
                    },
                )

            return result

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Record error in OTEL
            span = trace.get_current_span()
            if span.is_recording():
                span.set_attribute("dj.timing.duration_ms", elapsed_ms)
                span.set_attribute("dj.timing.success", False)
                span.set_attribute("dj.timing.method", method)
                span.record_exception(e)

            # Log error with timing
            if settings.debug:
                logger.warning(
                    "MCP operation failed",
                    extra={
                        "method": method,
                        "duration_ms": f"{elapsed_ms:.2f}",
                        "error": str(e),
                    },
                )

            raise


class StructuredLoggingMiddleware(Middleware):
    """Adds structured JSON logging for all MCP operations.

    Logs include:
    - MCP method name
    - Source (client/server)
    - Request type (request/notification)
    - Input parameters (if payload_logging enabled)
    - Result status (success/error)
    """

    async def on_message(
        self,
        context: MiddlewareContext[Any],
        call_next: CallNext[Any, Any],
    ) -> Any:
        """Log request and response with structured data."""
        method = context.method
        source = context.source
        msg_type = context.type

        # Log request
        log_data: dict[str, Any] = {
            "method": method,
            "source": source,
            "type": msg_type,
        }

        if settings.payload_logging and hasattr(context, "message"):
            log_data["params"] = getattr(context.message, "params", None)

        logger.info("MCP message", extra=log_data)

        try:
            result = await call_next(context)
            logger.info(
                "MCP success",
                extra={
                    "method": method,
                    "status": "success",
                },
            )
            return result

        except Exception as e:
            logger.error(
                "MCP error",
                extra={
                    "method": method,
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )
            raise
