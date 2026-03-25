"""Tests for custom FastMCP middleware."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.middleware import DetailedTimingMiddleware, StructuredLoggingMiddleware


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


@pytest.fixture
def mock_context():
    """Create a mock MiddlewareContext."""
    context = MagicMock()
    context.method = "tools/call"
    context.source = "client"
    context.type = "request"
    
    # Mock message with params
    message = MagicMock()
    message.params = {"arg1": "value1", "arg2": 42}
    context.message = message
    
    return context


class TestDetailedTimingMiddleware:
    """Test DetailedTimingMiddleware timing and OTEL integration."""

    async def test_records_timing_on_success(
        self, mock_context, span_exporter: InMemorySpanExporter
    ):
        """Middleware records timing in span on success."""
        tracer = trace.get_tracer("test")
        middleware = DetailedTimingMiddleware()

        async def call_next(ctx):
            with tracer.start_as_current_span("operation"):
                return {"status": "ok"}

        result = await middleware.on_message(mock_context, call_next)

        # Result should be returned unchanged
        assert result == {"status": "ok"}

        # Check OTEL span
        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert "dj.timing.duration_ms" in spans[0].attributes
        assert spans[0].attributes["dj.timing.success"] is True
        assert spans[0].attributes["dj.timing.method"] == "tools/call"

    async def test_records_timing_on_error(
        self, mock_context, span_exporter: InMemorySpanExporter
    ):
        """Middleware records timing and error in span when call_next fails."""
        tracer = trace.get_tracer("test")
        middleware = DetailedTimingMiddleware()

        async def call_next(ctx):
            with tracer.start_as_current_span("operation"):
                raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await middleware.on_message(mock_context, call_next)

        # Check OTEL span has error
        spans = span_exporter.get_finished_spans()
        assert len(spans) == 1
        assert "dj.timing.duration_ms" in spans[0].attributes
        assert spans[0].attributes["dj.timing.success"] is False


class TestStructuredLoggingMiddleware:
    """Test StructuredLoggingMiddleware request/response logging."""

    async def test_logs_request_and_response(self, mock_context, caplog):
        """Middleware logs request and successful response."""
        middleware = StructuredLoggingMiddleware()

        async def call_next(ctx):
            return {"status": "ok"}

        with caplog.at_level("INFO"):
            await middleware.on_message(mock_context, call_next)

        # Check request logged
        request_logs = [r for r in caplog.records if "MCP message" in r.message]
        assert len(request_logs) == 1
        assert request_logs[0].method == "tools/call"
        assert request_logs[0].source == "client"
        assert request_logs[0].type == "request"

        # Check response logged
        response_logs = [r for r in caplog.records if "MCP success" in r.message]
        assert len(response_logs) == 1
        assert response_logs[0].status == "success"

    async def test_logs_error(self, mock_context, caplog):
        """Middleware logs errors with error type and message."""
        middleware = StructuredLoggingMiddleware()

        async def call_next(ctx):
            raise RuntimeError("Test failure")

        with caplog.at_level("ERROR"):
            with pytest.raises(RuntimeError, match="Test failure"):
                await middleware.on_message(mock_context, call_next)

        # Check error logged
        error_logs = [r for r in caplog.records if "MCP error" in r.message]
        assert len(error_logs) == 1
        assert error_logs[0].status == "error"
        assert error_logs[0].error == "Test failure"
        assert error_logs[0].error_type == "RuntimeError"

    async def test_logs_params_when_payload_logging_enabled(self, mock_context, caplog, monkeypatch):
        """Middleware includes request params when payload_logging is True."""
        from app.config import settings

        monkeypatch.setattr(settings, "payload_logging", True)

        middleware = StructuredLoggingMiddleware()

        async def call_next(ctx):
            return {"status": "ok"}

        with caplog.at_level("INFO"):
            await middleware.on_message(mock_context, call_next)

        request_logs = [r for r in caplog.records if "MCP message" in r.message]
        assert len(request_logs) == 1
        assert hasattr(request_logs[0], "params")
        assert request_logs[0].params == {"arg1": "value1", "arg2": 42}
