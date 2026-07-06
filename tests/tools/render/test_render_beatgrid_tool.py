import pytest
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_render_beatgrid_tool_metadata(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    t = next(x for x in tools if x.name == "render_beatgrid")
    assert "namespace:render" in t.tags
