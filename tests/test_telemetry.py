"""Tests for OpenTelemetry instrumentation and custom spans."""

import pytest

otel_trace = pytest.importorskip("opentelemetry.trace", reason="opentelemetry SDK not installed")
otel_sdk = pytest.importorskip("opentelemetry.sdk.trace", reason="opentelemetry SDK not installed")

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from app.telemetry import (
    add_span_event,
    instrument_heavy_operation,
    record_error,
    set_span_attributes,
)


@pytest.fixture(scope="module")
def tracer_provider():
    """Set up a single tracer provider for the entire module."""
    provider = TracerProvider()
    trace.set_tracer_provider(provider)
    yield provider
    # Reset after all tests
    trace._TRACER_PROVIDER = None


@pytest.fixture
def span_exporter(tracer_provider):
    """Configure in-memory span exporter for testing."""
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    tracer_provider.add_span_processor(processor)
    yield exporter
    # Clear spans after each test
    exporter.clear()
    # Shutdown processor (proper cleanup)
    processor.shutdown()


class TestInstrumentHeavyOperation:
    """Test custom span decorator for heavy operations."""

    async def test_async_function_creates_span(self, span_exporter: InMemorySpanExporter):
        """Async function decorated with instrument_heavy_operation creates span."""

        @instrument_heavy_operation("test_operation")
        async def async_func(value: int) -> int:
            return value * 2

        result = await async_func(21)
        assert result == 42

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "dj.test_operation"
        assert spans[0].attributes["dj.operation"] == "test_operation"
        assert spans[0].attributes["dj.arg.0"] == 21

    def test_sync_function_creates_span(self, span_exporter: InMemorySpanExporter):
        """Sync function decorated with instrument_heavy_operation creates span."""

        @instrument_heavy_operation("sync_operation")
        def sync_func(value: str) -> str:
            return value.upper()

        result = sync_func("hello")
        assert result == "HELLO"

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "dj.sync_operation"
        assert spans[0].attributes["dj.operation"] == "sync_operation"
        assert spans[0].attributes["dj.arg.0"] == "hello"

    async def test_span_captures_kwargs(self, span_exporter: InMemorySpanExporter):
        """Span includes keyword arguments as attributes."""

        @instrument_heavy_operation("with_kwargs")
        async def func_with_kwargs(*, count: int, enabled: bool, name: str) -> None:
            pass

        await func_with_kwargs(count=42, enabled=True, name="test")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["dj.param.count"] == 42
        assert spans[0].attributes["dj.param.enabled"] is True
        assert spans[0].attributes["dj.param.name"] == "test"

    async def test_span_captures_list_count(self, span_exporter: InMemorySpanExporter):
        """Span records list argument count (not contents)."""

        @instrument_heavy_operation("with_list")
        async def func_with_list(items: list[str]) -> None:
            pass

        await func_with_list(items=["a", "b", "c"])

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["dj.param.items.count"] == 3

    async def test_span_records_exception(self, span_exporter: InMemorySpanExporter):
        """Span records exception and sets error status."""

        @instrument_heavy_operation("failing_operation")
        async def failing_func() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await failing_func()

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code.name == "ERROR"
        assert "Test error" in spans[0].status.description

        # Check exception event
        events = spans[0].events
        assert any("exception" in e.name.lower() for e in events)


class TestSpanHelpers:
    """Test helper functions for span manipulation."""

    def test_add_span_event(self, span_exporter: InMemorySpanExporter):
        """add_span_event adds event to current span."""
        tracer = trace.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            add_span_event("custom_event", {"key": "value", "count": 42})

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1

        events = spans[0].events
        assert len(events) == 1
        assert events[0].name == "custom_event"
        assert events[0].attributes["key"] == "value"
        assert events[0].attributes["count"] == 42

    def test_set_span_attributes(self, span_exporter: InMemorySpanExporter):
        """set_span_attributes adds attributes to current span."""
        tracer = trace.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            set_span_attributes(track_count=50, duration_min=90, enabled=True)

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].attributes["dj.track_count"] == 50
        assert spans[0].attributes["dj.duration_min"] == 90
        assert spans[0].attributes["dj.enabled"] is True

    def test_record_error(self, span_exporter: InMemorySpanExporter):
        """record_error records exception without raising."""
        tracer = trace.get_tracer("test")

        with tracer.start_as_current_span("test_span"):
            try:
                raise RuntimeError("Something went wrong")
            except RuntimeError as e:
                record_error(e, "Additional context")

        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code.name == "ERROR"
        assert "Additional context" in spans[0].status.description

        # Check exception was recorded
        events = spans[0].events
        exception_events = [e for e in events if "exception" in e.name.lower()]
        assert len(exception_events) == 1

        # Check context event
        context_events = [e for e in events if e.name == "error_context"]
        assert len(context_events) == 1
        assert context_events[0].attributes["message"] == "Additional context"


class TestMiddlewareCompatibility:
    """Test that telemetry works with FastMCP middleware."""

    async def test_no_op_without_sdk(self):
        """Telemetry functions are no-ops when SDK not configured."""
        # Reset tracer provider to no-op
        trace.set_tracer_provider(trace.NoOpTracerProvider())

        @instrument_heavy_operation("no_op_test")
        async def func() -> str:
            add_span_event("event")
            set_span_attributes(key="value")
            return "success"

        result = await func()
        assert result == "success"  # No errors, operations are no-ops
