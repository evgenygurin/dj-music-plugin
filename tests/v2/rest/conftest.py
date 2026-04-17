"""FastAPI TestClient fixture with mocked MCP."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.v2.rest.app import build_rest_app
from app.v2.rest.state import ApiRuntimeState


@pytest.fixture
def mock_mcp():
    mcp = MagicMock()
    tool = MagicMock()
    tool.name = "entity_list"
    tool.description = "list"
    tool.tags = {"core"}
    mcp.list_tools = AsyncMock(return_value=[tool])
    mcp.get_tool = AsyncMock(return_value=tool)
    call_result = MagicMock()
    call_result.structured_content = {"items": [1, 2]}
    call_result.data = None
    call_result.content = []
    mcp.call_tool = AsyncMock(return_value=call_result)
    return mcp


@pytest.fixture
def rest_client(mock_mcp):
    app = build_rest_app()

    @asynccontextmanager
    async def _fake_lifespan(app):
        app.state.runtime = ApiRuntimeState(mcp=mock_mcp, mcp_ready=True)
        yield

    app.router.lifespan_context = _fake_lifespan
    with TestClient(app) as client:
        yield client
