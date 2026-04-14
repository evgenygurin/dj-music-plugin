"""Tests for the MCP server builder."""

from __future__ import annotations

from app.bootstrap.server_builder import build_mcp_server


def test_build_mcp_server_registers_expected_middleware() -> None:
    """The builder should preserve middleware ordering."""
    mcp = build_mcp_server()
    middleware_names = [type(middleware).__name__ for middleware in mcp.middleware]

    assert middleware_names[-5:] == [
        "StructuredLoggingMiddleware",
        "DetailedTimingMiddleware",
        "YMRateLimitMiddleware",
        "ErrorHandlingMiddleware",
        "RetryMiddleware",
    ]


def test_build_mcp_server_registers_resource_and_prompt_transforms() -> None:
    """The builder should keep resource/prompt transforms and visibility disables."""
    mcp = build_mcp_server()
    transform_names = [type(transform).__name__ for transform in mcp.transforms]

    # BM25SearchTransform was removed — only ResourcesAsTools + PromptsAsTools remain
    assert "ResourcesAsTools" in transform_names
    assert "PromptsAsTools" in transform_names

    visibility_reprs = [
        repr(transform) for transform in mcp.transforms if type(transform).__name__ == "Visibility"
    ]
    # All 7 toggleable categories are disabled at startup
    assert any("memory" in text for text in visibility_reprs)
    assert any("ym" in text for text in visibility_reprs)
