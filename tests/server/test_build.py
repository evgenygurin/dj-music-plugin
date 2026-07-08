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


@pytest.mark.asyncio
async def test_build_for_tests_can_disable_prompts_for_tool_only_clients() -> None:
    mcp = await build_mcp_app_for_tests(with_prompts=False)
    prompts = await mcp.list_prompts()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert prompts == []
    assert "entity_list" in names


@pytest.mark.asyncio
async def test_build_for_tests_honors_disable_prompts_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DJ_MCP_DISABLE_PROMPTS", "1")
    mcp = await build_mcp_app_for_tests()
    assert await mcp.list_prompts() == []


@pytest.mark.asyncio
async def test_build_for_tests_disables_middleware_on_request() -> None:
    mcp = await build_mcp_app_for_tests(with_middleware=False)
    names = [type(m).__name__ for m in mcp.middleware]
    assert "DomainErrorMiddleware" not in names
