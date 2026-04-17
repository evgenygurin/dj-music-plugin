"""Shared fixtures for prompt tests.

Prompts are pure functions — fixtures are minimal. We still use the
in-memory Client so we exercise the actual @prompt registration path.

NOTE (Phase 4): Client-based tests xfail until Phase 5 provides
``build_mcp_app_for_tests``. Pure function tests on the prompt modules
themselves run unconditionally.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio


@pytest_asyncio.fixture
async def mcp_app() -> AsyncIterator[object]:
    """Phase 5 stub — FastMCP app builder not yet implemented."""
    try:
        from app.v2.server.app import build_mcp_app_for_tests  # type: ignore[import-not-found]
    except ImportError:
        pytest.xfail("Phase 5 server wiring: build_mcp_app_for_tests missing")
        yield None
        return

    app = await build_mcp_app_for_tests()
    yield app


@pytest_asyncio.fixture
async def client(mcp_app: object) -> AsyncIterator[object]:
    """In-memory FastMCP client. XFailed until Phase 5."""
    try:
        from fastmcp.client import Client  # type: ignore[import-not-found]
    except ImportError:
        pytest.xfail("Phase 5 server wiring: fastmcp.client unavailable")
        yield None
        return

    async with Client(mcp_app) as c:  # type: ignore[arg-type]
        yield c
