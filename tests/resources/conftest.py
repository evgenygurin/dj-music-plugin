"""Shared fixtures for resource tests.

Provides:
- ``mcp_app`` — a FastMCP server with all resources registered.
- ``client`` — in-memory FastMCP Client bound to ``mcp_app``.
- ``seeded_db`` — UoW with seed tracks + playlist + set + features.
- ``session_store`` — in-memory session state (set draft, tool history, energy samples).

NOTE (Phase 4): ``mcp_app`` / ``client`` depend on Phase 5 server wiring
(``app.server.app.build_mcp_app_for_tests``). Until Phase 5 composes
the FastMCP instance, tests that use these fixtures are marked
``xfail(reason="Phase 5 server wiring")``. The non-Client fixtures
(``session_store``) are usable now.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app.server.session_store import InMemorySessionStore


@pytest_asyncio.fixture
async def mcp_app() -> AsyncIterator[object]:
    """Phase 5 stub — FastMCP app builder not yet implemented."""
    try:
        from app.server.app import build_mcp_app_for_tests  # type: ignore[import-not-found]
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


@pytest_asyncio.fixture
async def seeded_db() -> AsyncIterator[object]:
    """Phase 5 stub — canonical UoW seed depends on repository methods
    introduced in Phase 5 (``create(id=...)``, ``add_items``, ``list_from``,
    ``search_by_bpm_range``). Marked xfail until those land.
    """
    pytest.xfail("Phase 5 server wiring: seeded UoW repositories incomplete")
    yield None


@pytest.fixture
def session_store() -> InMemorySessionStore:
    return InMemorySessionStore()
