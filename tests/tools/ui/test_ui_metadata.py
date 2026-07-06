"""Metadata tests for the 7 Prefab UI tools.

Each tool must:

- Register with name ``ui_*``.
- Carry tag ``namespace:ui:read`` + ``ui`` + ``read``.
- Have ``meta={"ui": True}`` — the standalone-decorator equivalent of
  ``@mcp.tool(app=True)`` (FastMCP merges this into the ``AppConfig``
  wire format for Prefab-aware clients).
- Be read-only + idempotent (annotations).
"""

from __future__ import annotations

import pytest
from fastmcp import FastMCP

UI_TOOL_NAMES: tuple[str, ...] = (
    "ui_set_view",
    "ui_transition_score",
    "ui_library_audit",
    "ui_score_pool_matrix",
    "ui_library_dashboard",
    "ui_camelot_wheel",
    "ui_render_studio",
)


@pytest.mark.asyncio
async def test_all_ui_tools_registered(mcp_server: FastMCP) -> None:
    tools = await mcp_server.list_tools()
    names = {t.name for t in tools}
    missing = [n for n in UI_TOOL_NAMES if n not in names]
    assert not missing, f"Missing UI tools: {missing}"


@pytest.mark.asyncio
async def test_ui_tools_have_correct_tags_and_meta(mcp_server: FastMCP) -> None:
    tools = {t.name: t for t in await mcp_server.list_tools()}
    for name in UI_TOOL_NAMES:
        t = tools[name]
        tags = set(t.tags or set())
        assert "namespace:ui:read" in tags, f"{name} missing namespace:ui:read"
        assert "ui" in tags, f"{name} missing ui tag"
        assert "read" in tags, f"{name} missing read tag"
        assert t.meta is not None, f"{name} meta is None"
        # FastMCP transforms ``meta={"ui": True}`` into an AppConfig wire payload
        # that points at a Prefab renderer resource URI. The ``ui`` key must
        # exist — its shape signals Prefab Apps extension support to the client.
        ui_meta = t.meta.get("ui")
        assert ui_meta is not None, f"{name} meta.ui missing — app=True wiring broken"
        # Either True (raw decorator form) or a dict with a resourceUri (after
        # FastMCP post-processes the registration).
        assert ui_meta is True or (isinstance(ui_meta, dict) and "resourceUri" in ui_meta), (
            f"{name} meta.ui unexpected shape: {ui_meta!r}"
        )


@pytest.mark.asyncio
async def test_ui_tools_are_readonly_idempotent(mcp_server: FastMCP) -> None:
    tools = {t.name: t for t in await mcp_server.list_tools()}
    for name in UI_TOOL_NAMES:
        ann = tools[name].annotations
        assert ann is not None, f"{name} missing annotations"
        assert ann.readOnlyHint is True, f"{name} readOnlyHint != True"
        assert ann.idempotentHint is True, f"{name} idempotentHint != True"
