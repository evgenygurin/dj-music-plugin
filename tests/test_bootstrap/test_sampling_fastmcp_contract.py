"""Contract tests for FastMCP sampling wiring (see https://gofastmcp.com/servers/sampling)."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from app.bootstrap.sampling import build_sampling_handler
from app.bootstrap.server_builder import build_mcp_server
from app.config import settings


def test_fastmcp_defaults_sampling_behavior_to_fallback() -> None:
    """When ``sampling_handler_behavior`` is omitted, FastMCP uses ``fallback``."""
    mcp = FastMCP("test", sampling_handler=None)
    assert mcp.sampling_handler is None
    assert mcp.sampling_handler_behavior == "fallback"


def test_build_mcp_server_uses_sampling_behavior_fallback() -> None:
    """Production server matches docs: explicit ``sampling_handler_behavior=\"fallback\"``."""
    mcp = build_mcp_server()
    assert mcp.sampling_handler_behavior == "fallback"


def test_build_sampling_handler_none_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert build_sampling_handler() is None


def test_build_sampling_handler_creates_anthropic_when_key_and_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With key + ``anthropic`` installed (``--extra llm``), handler matches FastMCP docs."""
    pytest.importorskip("anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-test-contract-only")
    h = build_sampling_handler()
    assert h is not None
    assert type(h).__name__ == "AnthropicSamplingHandler"
