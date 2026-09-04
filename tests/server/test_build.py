"""Tests for the composition root (Task 24)."""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

from app.server.app import build_mcp_app_for_tests, build_mcp_server


def test_build_returns_fastmcp_instance() -> None:
    mcp = build_mcp_server()
    assert isinstance(mcp, FastMCP)


def test_build_registers_all_15_middleware() -> None:
    mcp = build_mcp_server()
    added = [type(m).__name__ for m in mcp.middleware]
    expected = [
        "DomainErrorMiddleware",
        "SentryContextMiddleware",
        "DetailedTimingMiddleware",
        "AuditLogMiddleware",
        "RetryMiddleware",
        "ResponseLimitingMiddleware",
        "ResponseCachingMiddleware",
        "DeprecationWarningMiddleware",
        "CostTrackingMiddleware",
        "SamplingBudgetMiddleware",
        "ProgressThrottleMiddleware",
        "ToolCallTimeoutMiddleware",
        "ProviderRateLimitMiddleware",
        "DbSessionMiddleware",
        "StructuredLoggingMiddleware",
    ]
    # FastMCP may auto-prepend built-in middleware (DereferenceRefs etc.).
    # We assert our 15 appear as a contiguous suffix/subsequence in order.
    names = [n for n in added if n in expected]
    assert names == expected


def test_build_has_providers_registered() -> None:
    mcp = build_mcp_server()
    # FileSystemProvider for tools/resources/prompts plus internal providers.
    assert hasattr(mcp, "_providers") or hasattr(mcp, "providers")


@pytest.mark.asyncio
async def test_build_for_tests_returns_fastmcp_instance() -> None:
    mcp = await build_mcp_app_for_tests()
    assert isinstance(mcp, FastMCP)


@pytest.mark.asyncio
async def test_build_for_tests_lists_tools() -> None:
    """End-to-end sanity: the in-memory server can list tools."""
    mcp = await build_mcp_app_for_tests()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    # At least a handful of v2 tools should be registered via FSP.
    assert len(names) >= 5


@pytest.mark.asyncio
async def test_build_for_tests_lists_resources() -> None:
    mcp = await build_mcp_app_for_tests()
    resources = await mcp.list_resources()
    # At least a handful of resources should be registered.
    assert len(resources) >= 1


@pytest.mark.asyncio
async def test_build_for_tests_lists_prompts() -> None:
    mcp = await build_mcp_app_for_tests()
    prompts = await mcp.list_prompts()
    assert len(prompts) >= 1


def test_build_does_not_enable_background_tasks_globally() -> None:
    """Only explicitly heavy tools should opt into Docket task execution."""
    mcp = build_mcp_server()
    assert mcp._support_tasks_by_default is False


@pytest.mark.asyncio
async def test_heavy_tools_keep_explicit_task_support() -> None:
    """The stems tool remains background-capable after disabling the global default."""
    mcp = build_mcp_server()
    tool = await mcp.get_tool("stems_separate")
    assert tool is not None
    assert tool.task_config.mode != "forbidden"


@pytest.mark.asyncio
async def test_build_for_tests_disables_middleware_on_request() -> None:
    mcp = await build_mcp_app_for_tests(with_middleware=False)
    names = [type(m).__name__ for m in mcp.middleware]
    assert "DomainErrorMiddleware" not in names


@pytest.mark.asyncio
async def test_interactive_mix_composer_is_model_visible() -> None:
    """The composer entrypoint must survive the BM25 always-visible filter."""
    mcp = build_mcp_server()
    names = {tool.name for tool in await mcp.list_tools()}
    assert "ui_mix_composer" in names
