import pytest

from app.server.app import build_mcp_app_for_tests


@pytest.mark.asyncio
async def test_server_builds_with_tasks_enabled():
    mcp = await build_mcp_app_for_tests()
    assert mcp is not None
