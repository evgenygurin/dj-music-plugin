"""Tests for custom MCP middleware.

Tests cover:
- YMRateLimitMiddleware (YM-specific rate limiting)
- StructuredLoggingMiddleware (JSON logging)
- DetailedTimingMiddleware (per-operation timing)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
from unittest.mock import Mock

import pytest

# Note: Due to typing_extensions version compatibility issues with FastMCP dependencies,
# we create a minimal mock for MiddlewareContext rather than importing from fastmcp.
# This allows us to test our custom middleware logic without the full FastMCP stack.


class MockMiddlewareContext:
    """Minimal mock for MiddlewareContext to avoid import issues."""

    def __init__(self) -> None:
        self.method = "tools/call"
        self.source = "client"
        self.type = "request"
        self.message = Mock()
        self.message.name = "test_tool"
        self.message.uri = "test://resource"
        self.timestamp = None
        self.fastmcp_context = None


# Import middleware (all classes in one file now)
from dj_music.middleware import (
    DetailedTimingMiddleware,
    StructuredLoggingMiddleware,
    YMRateLimitMiddleware,
)

# ── Fixtures ─────────────────────────────────────────


@pytest.fixture
def mock_context() -> MockMiddlewareContext:
    """Create a mock MiddlewareContext for testing."""
    return MockMiddlewareContext()


@pytest.fixture
def mock_call_next() -> Any:
    """Create a mock call_next function."""

    async def _call_next(context: MockMiddlewareContext) -> dict:
        await asyncio.sleep(0.01)  # Simulate processing
        return {"result": "success"}

    return _call_next


# ── YMRateLimitMiddleware Tests ──────────────────────


@pytest.mark.asyncio
async def test_ym_rate_limit_non_ym_tool(
    mock_context: MockMiddlewareContext, mock_call_next: Any
) -> None:
    """Non-YM tools should pass through without delay."""
    middleware = YMRateLimitMiddleware(delay_seconds=1.0)
    mock_context.message.name = "list_tracks"  # Not a YM tool

    start = time.monotonic()
    result = await middleware.on_call_tool(mock_context, mock_call_next)
    elapsed = time.monotonic() - start

    assert result == {"result": "success"}
    assert elapsed < 0.5  # Should be fast (< 0.5s)


@pytest.mark.asyncio
async def test_ym_rate_limit_first_call(
    mock_context: MockMiddlewareContext, mock_call_next: Any
) -> None:
    """First YM tool call should not be delayed."""
    middleware = YMRateLimitMiddleware(delay_seconds=1.0)
    mock_context.message.name = "ym_search"

    start = time.monotonic()
    result = await middleware.on_call_tool(mock_context, mock_call_next)
    elapsed = time.monotonic() - start

    assert result == {"result": "success"}
    assert elapsed < 0.5  # Should be fast (< 0.5s)


@pytest.mark.asyncio
async def test_ym_rate_limit_consecutive_calls(
    mock_context: MockMiddlewareContext, mock_call_next: Any
) -> None:
    """Consecutive YM tool calls should be rate limited."""
    delay_seconds = 0.2
    middleware = YMRateLimitMiddleware(delay_seconds=delay_seconds)
    mock_context.message.name = "ym_search"

    # First call
    await middleware.on_call_tool(mock_context, mock_call_next)

    # Second call should be delayed
    start = time.monotonic()
    await middleware.on_call_tool(mock_context, mock_call_next)
    elapsed = time.monotonic() - start

    # Should have waited at least delay_seconds minus the processing time
    assert elapsed >= delay_seconds * 0.8  # Allow 20% margin


@pytest.mark.asyncio
async def test_ym_rate_limit_mixed_tools(
    mock_context: MockMiddlewareContext, mock_call_next: Any
) -> None:
    """YM rate limit should only apply to YM tools."""
    middleware = YMRateLimitMiddleware(delay_seconds=0.2)

    # First YM call
    mock_context.message.name = "ym_search"
    await middleware.on_call_tool(mock_context, mock_call_next)

    # Non-YM call should not be delayed
    mock_context.message.name = "list_tracks"
    start = time.monotonic()
    await middleware.on_call_tool(mock_context, mock_call_next)
    elapsed = time.monotonic() - start
    assert elapsed < 0.1

    # Second YM call should be delayed from first YM call
    mock_context.message.name = "ym_get_tracks"
    start = time.monotonic()
    await middleware.on_call_tool(mock_context, mock_call_next)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.15  # Should have waited


@pytest.mark.asyncio
async def test_ym_rate_limit_is_ym_tool_detection() -> None:
    """Test _is_ym_tool detection logic."""
    middleware = YMRateLimitMiddleware()

    assert middleware._is_ym_tool("ym_search")
    assert middleware._is_ym_tool("ym_get_tracks")
    assert middleware._is_ym_tool("ym_playlists")
    assert not middleware._is_ym_tool("list_tracks")
    assert not middleware._is_ym_tool("build_set")
    assert not middleware._is_ym_tool("analyze_track")


# ── StructuredLoggingMiddleware Tests ────────────────


@pytest.mark.asyncio
async def test_structured_logging_basic(
    mock_context: MockMiddlewareContext,
    mock_call_next: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test basic structured logging without payloads."""
    caplog.set_level(logging.INFO)
    middleware = StructuredLoggingMiddleware(include_payloads=False)

    result = await middleware.on_message(mock_context, mock_call_next)

    assert result == {"result": "success"}
    assert len(caplog.records) == 1

    log_record = caplog.records[0]
    log_data = json.loads(log_record.message)

    assert log_data["method"] == "tools/call"
    assert log_data["source"] == "client"
    assert log_data["type"] == "request"
    assert "timestamp" in log_data
    assert "duration_ms" in log_data
    assert log_data["duration_ms"] > 0
    assert "request" not in log_data  # Payloads not included
    assert "response" not in log_data


@pytest.mark.asyncio
async def test_structured_logging_with_payloads(
    mock_context: MockMiddlewareContext,
    mock_call_next: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test structured logging with payloads included."""
    caplog.set_level(logging.INFO)
    middleware = StructuredLoggingMiddleware(include_payloads=True, max_payload_length=100)

    result = await middleware.on_message(mock_context, mock_call_next)

    assert result == {"result": "success"}
    log_data = json.loads(caplog.records[0].message)

    assert "request" in log_data
    assert "response" in log_data


@pytest.mark.asyncio
async def test_structured_logging_truncation(
    mock_context: MockMiddlewareContext, caplog: pytest.LogCaptureFixture
) -> None:
    """Test payload truncation for large responses."""
    caplog.set_level(logging.INFO)
    middleware = StructuredLoggingMiddleware(include_payloads=True, max_payload_length=50)

    async def large_response(_context: MockMiddlewareContext) -> dict:
        return {"data": "x" * 1000}  # Large response

    await middleware.on_message(mock_context, large_response)

    log_data = json.loads(caplog.records[0].message)
    assert len(log_data["response"]) <= 53  # 50 + "..." = 53


@pytest.mark.asyncio
async def test_structured_logging_error(
    mock_context: MockMiddlewareContext, caplog: pytest.LogCaptureFixture
) -> None:
    """Test structured logging on error."""
    caplog.set_level(logging.ERROR)
    middleware = StructuredLoggingMiddleware(include_payloads=False)

    async def failing_call(_context: MockMiddlewareContext) -> None:
        raise ValueError("Test error")

    with pytest.raises(ValueError, match="Test error"):
        await middleware.on_message(mock_context, failing_call)

    assert len(caplog.records) == 1
    log_data = json.loads(caplog.records[0].message)

    assert "error" in log_data
    assert log_data["error"]["type"] == "ValueError"
    assert log_data["error"]["message"] == "Test error"
    assert "duration_ms" in log_data


# ── DetailedTimingMiddleware Tests ───────────────────


@pytest.mark.asyncio
async def test_detailed_timing_tool(
    mock_context: MockMiddlewareContext,
    mock_call_next: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test timing for tool execution."""
    caplog.set_level(logging.INFO)
    middleware = DetailedTimingMiddleware()
    mock_context.message.name = "test_tool"

    result = await middleware.on_call_tool(mock_context, mock_call_next)

    assert result == {"result": "success"}
    assert any("Tool timing: test_tool completed" in r.message for r in caplog.records)
    # Extract timing from log
    timing_record = next(r for r in caplog.records if "Tool timing: test_tool" in r.message)
    assert "ms" in timing_record.message
    assert "completed" in timing_record.message


@pytest.mark.asyncio
async def test_detailed_timing_resource(
    mock_context: MockMiddlewareContext,
    mock_call_next: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test timing for resource reads."""
    caplog.set_level(logging.INFO)
    middleware = DetailedTimingMiddleware()
    mock_context.message.uri = "test://resource"

    result = await middleware.on_read_resource(mock_context, mock_call_next)

    assert result == {"result": "success"}
    assert any("Resource timing: test://resource read" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_detailed_timing_prompt(
    mock_context: MockMiddlewareContext,
    mock_call_next: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test timing for prompt retrieval."""
    caplog.set_level(logging.INFO)
    middleware = DetailedTimingMiddleware()
    mock_context.message.name = "test_prompt"

    result = await middleware.on_get_prompt(mock_context, mock_call_next)

    assert result == {"result": "success"}
    assert any("Prompt timing: test_prompt retrieved" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_detailed_timing_request(
    mock_context: MockMiddlewareContext,
    mock_call_next: Any,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test timing for overall request."""
    caplog.set_level(logging.DEBUG)
    middleware = DetailedTimingMiddleware()
    mock_context.method = "tools/call"

    result = await middleware.on_request(mock_context, mock_call_next)

    assert result == {"result": "success"}
    assert any("Request timing: tools/call completed" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_detailed_timing_tool_failure(
    mock_context: MockMiddlewareContext, caplog: pytest.LogCaptureFixture
) -> None:
    """Test timing logs error on tool failure."""
    caplog.set_level(logging.WARNING)
    middleware = DetailedTimingMiddleware()
    mock_context.message.name = "failing_tool"

    async def failing_call(_context: MockMiddlewareContext) -> None:
        await asyncio.sleep(0.01)
        raise RuntimeError("Tool failed")

    with pytest.raises(RuntimeError, match="Tool failed"):
        await middleware.on_call_tool(mock_context, failing_call)

    assert any("Tool timing: failing_tool failed" in r.message for r in caplog.records)
    timing_record = next(r for r in caplog.records if "Tool timing: failing_tool" in r.message)
    assert "ms" in timing_record.message
    assert "failed" in timing_record.message


# ── Integration Test ─────────────────────────────────


@pytest.mark.asyncio
async def test_middleware_chain_integration(
    mock_context: MockMiddlewareContext, caplog: pytest.LogCaptureFixture
) -> None:
    """Test middleware chain with multiple middleware."""
    caplog.set_level(logging.INFO)

    # Create middleware chain
    ym_rate_limiter = YMRateLimitMiddleware(delay_seconds=0.1)
    structured_logger = StructuredLoggingMiddleware(include_payloads=False)
    detailed_timer = DetailedTimingMiddleware()

    async def final_handler(_context: MockMiddlewareContext) -> dict:
        await asyncio.sleep(0.01)
        return {"result": "success"}

    # Chain: structured_logger → detailed_timer → ym_rate_limiter → handler
    async def chain_layer_1(ctx: MockMiddlewareContext) -> dict:
        return await ym_rate_limiter.on_call_tool(ctx, final_handler)

    async def chain_layer_2(ctx: MockMiddlewareContext) -> dict:
        return await detailed_timer.on_call_tool(ctx, chain_layer_1)

    async def chain_layer_3(ctx: MockMiddlewareContext) -> dict:
        return await structured_logger.on_message(ctx, chain_layer_2)

    mock_context.message.name = "test_tool"
    result = await chain_layer_3(mock_context)

    assert result == {"result": "success"}

    # Check that both middleware logged
    assert any("Tool timing: test_tool" in r.message for r in caplog.records)
    # Structured logging should produce JSON
    json_logs = [r for r in caplog.records if r.message.startswith("{")]
    assert len(json_logs) >= 1
