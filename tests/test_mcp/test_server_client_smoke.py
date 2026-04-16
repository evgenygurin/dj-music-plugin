"""In-memory FastMCP client smoke tests (transport + tool round-trip).

Pattern: https://gofastmcp.com/development/tests (in-memory ``Client(mcp)``).
"""

from __future__ import annotations

import pytest
from fastmcp import Client

from app.server import mcp


@pytest.mark.asyncio
async def test_unlock_tools_status_via_in_memory_client() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "unlock_tools",
            {"action": "status"},
        )
        data = result.structured_content
        assert data is not None
        assert data.get("action") == "status"
        assert "effective" in data
