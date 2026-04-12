"""Tests for the MCP server builder."""

from __future__ import annotations

from dj_music.di.server_builder import build_mcp_server


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


def test_build_mcp_server_registers_search_and_visibility_transforms() -> None:
    """The builder should keep search/resource/prompt transforms and visibility disables."""
    mcp = build_mcp_server()
    transform_names = [type(transform).__name__ for transform in mcp.transforms]

    assert transform_names[:3] == [
        "BM25SearchTransform",
        "ResourcesAsTools",
        "PromptsAsTools",
    ]

    visibility_reprs = [repr(transform) for transform in mcp.transforms if type(transform).__name__ == "Visibility"]
    assert any("tags={'atomic'}" in text for text in visibility_reprs)
    assert any("names={'_bm25_call_tool'}" in text for text in visibility_reprs)
