import pytest
from fastmcp import FastMCP


@pytest.mark.asyncio
async def test_render_mixdown_and_diagnose_registered(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    by_name = {t.name: t for t in tools}
    assert "namespace:render" in by_name["render_mixdown"].tags
    assert "namespace:render" in by_name["render_diagnose"].tags
