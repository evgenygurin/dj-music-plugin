"""Registration + always-visible tests for ui_render_studio (Plan 3 Task 4).

``ui_render_studio`` is the interactive Prefab studio entry tool — it must be
in ``ALWAYS_VISIBLE_TOOLS`` so Prefab-aware clients discover it without a BM25
query. Its ``render_studio_panel`` helper carries ``visibility=["app"]`` — it is
registered on the server (so the UI can ``CallTool`` it) but hidden from the
model / BM25, hence intentionally NOT in ``ALWAYS_VISIBLE_TOOLS``.
"""

from __future__ import annotations

import pytest

from app.server.app import build_mcp_app_for_tests
from app.server.transforms import ALWAYS_VISIBLE_TOOLS


def test_ui_render_studio_always_visible() -> None:
    assert "ui_render_studio" in ALWAYS_VISIBLE_TOOLS
    # helper is app-visibility only — never whitelisted for the model / BM25.
    assert "render_studio_panel" not in ALWAYS_VISIBLE_TOOLS


@pytest.mark.asyncio
async def test_ui_render_studio_registered_and_helper_present() -> None:
    mcp = await build_mcp_app_for_tests()
    names = {t.name for t in await mcp.list_tools()}
    # entry tool is model-visible.
    assert "ui_render_studio" in names
    # helper is app-visibility only — hidden from list_tools (model / BM25) ...
    assert "render_studio_panel" not in names
    # ... but still registered on the server so the UI can CallTool it.
    assert (await mcp.get_tool("render_studio_panel")).name == "render_studio_panel"
