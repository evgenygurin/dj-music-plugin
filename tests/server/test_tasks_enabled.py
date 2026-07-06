import pytest

from app.server.app import build_mcp_app_for_tests


@pytest.mark.asyncio
async def test_server_builds_with_tasks_enabled():
    mcp = await build_mcp_app_for_tests()
    assert mcp is not None


@pytest.mark.asyncio
async def test_render_tools_registered():
    mcp = await build_mcp_app_for_tests()
    tools = await mcp.list_tools()
    names = {t.name for t in tools}
    assert {"render_beatgrid", "render_mixdown", "render_diagnose"} <= names
