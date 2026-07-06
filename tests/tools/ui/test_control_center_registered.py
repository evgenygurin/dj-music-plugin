"""Registration + always-visible tests for ui_control_center (Phase 1 Task 4).

``ui_control_center`` is the interactive Prefab control-center entry tool — it
must be in ``ALWAYS_VISIBLE_TOOLS`` so Prefab-aware clients discover it without
a BM25 query. It reuses the already-hidden ``render_studio_panel`` helper for
its render actions (no new helper), so this task adds no new app-only tool.
"""

from __future__ import annotations

import pytest

from app.server.app import build_mcp_app_for_tests
from app.server.transforms import ALWAYS_VISIBLE_TOOLS


def test_ui_control_center_always_visible() -> None:
    assert "ui_control_center" in ALWAYS_VISIBLE_TOOLS


@pytest.mark.asyncio
async def test_ui_control_center_registered() -> None:
    mcp = await build_mcp_app_for_tests()
    names = {t.name for t in await mcp.list_tools()}
    assert "ui_control_center" in names
