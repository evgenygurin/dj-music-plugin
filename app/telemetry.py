"""OpenTelemetry instrumentation for DJ Music Plugin.

FastMCP provides native OTEL integration via opentelemetry-api.
This module adds custom spans for heavy operations (set building, audio analysis, delivery).

Usage:
    from app.telemetry import instrument_heavy_operation

    @instrument_heavy_operation("build_set")
    async def build_set_service(...):
        ...
"""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.config import settings

T = TypeVar("T")


def _get_tracer() -> trace.Tracer:
    """Get tracer lazily (allows test fixtures to configure provider first)."""
    return trace.get_tracer("dj-music-plugin", "0.1.0")


def instrument_heavy_operation(
    operation_name: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator to instrument heavy operations with custom spans.

    Args:
        operation_name: Name of the operation (e.g., "build_set", "analyze_batch")

    Returns:
        Decorated function with span tracking

    Example:
        @instrument_heavy_operation("optimize_set")
        async def optimize_set(tracks: list[Track]) -> SetVersion:
            ...
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = _get_tracer()
            with tracer.start_as_current_span(
                f"dj.{operation_name}",
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                # Add operation metadata
                span.set_attribute("dj.operation", operation_name)
                span.set_attribute("dj.debug_mode", settings.debug)

                # Add relevant args as attributes (first 3 positional args)
                for i, arg in enumerate(args[:3]):
                    if isinstance(arg, (str, int, float, bool)):
                        span.set_attribute(f"dj.arg.{i}", arg)

                # Add relevant kwargs
                for key, value in kwargs.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"dj.param.{key}", value)
                    elif isinstance(value, list) and value:
                        span.set_attribute(f"dj.param.{key}.count", len(value))

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracer = _get_tracer()
            with tracer.start_as_current_span(
                f"dj.{operation_name}",
                kind=trace.SpanKind.INTERNAL,
            ) as span:
                span.set_attribute("dj.operation", operation_name)
                span.set_attribute("dj.debug_mode", settings.debug)

                for i, arg in enumerate(args[:3]):
                    if isinstance(arg, (str, int, float, bool)):
                        span.set_attribute(f"dj.arg.{i}", arg)

                for key, value in kwargs.items():
                    if isinstance(value, (str, int, float, bool)):
                        span.set_attribute(f"dj.param.{key}", value)
                    elif isinstance(value, list) and value:
                        span.set_attribute(f"dj.param.{key}.count", len(value))

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def add_span_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    """Add an event to the current span (if active).

    Args:
        name: Event name (e.g., "ga_generation_complete", "track_analyzed")
        attributes: Optional attributes to attach to the event

    Example:
        add_span_event("ga_generation", {"generation": 42, "best_score": 0.85})
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.add_event(name, attributes or {})


def set_span_attributes(**attributes: Any) -> None:
    """Set attributes on the current span (if active).

    Args:
        **attributes: Key-value pairs to set as span attributes

    Example:
        set_span_attributes(track_count=50, total_duration_min=90)
    """
    span = trace.get_current_span()
    if span.is_recording():
        for key, value in attributes.items():
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(f"dj.{key}", value)


def record_error(exception: Exception, message: str | None = None) -> None:
    """Record an error on the current span without failing.

    Args:
        exception: The exception that occurred
        message: Optional additional context message

    Example:
        try:
            analyze_track(track_id)
        except AnalyzerUnavailableError as e:
            record_error(e, "Librosa not installed")
    """
    span = trace.get_current_span()
    if span.is_recording():
        span.record_exception(exception)
        if message:
            span.add_event("error_context", {"message": message})
        span.set_status(Status(StatusCode.ERROR, message or str(exception)))
