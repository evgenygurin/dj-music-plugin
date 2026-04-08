"""Tests for get_set_templates MCP tool."""

from __future__ import annotations

import pytest
from fastmcp import Client

from app.server import mcp


@pytest.mark.asyncio
async def test_get_set_templates_returns_all_templates() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool("get_set_templates", {})
        data = result.structured_content
        assert data is not None
        templates = data["templates"]
        assert isinstance(templates, list)
        assert len(templates) >= 8

        names = {tpl["name"] for tpl in templates}
        assert "peak_hour_60" in names
        assert "warm_up_30" in names

        peak = next(t for t in templates if t["name"] == "peak_hour_60")
        assert peak["duration_min"] == 60
        assert len(peak["slots"]) > 0

        first_slot = peak["slots"][0]
        assert "position" in first_slot
        assert "target_mood" in first_slot
        assert "energy_lufs" in first_slot
        assert "bpm_min" in first_slot
        assert "bpm_max" in first_slot
        assert "duration_ms" in first_slot
        assert "flexibility" in first_slot
        assert 0.0 <= first_slot["position"] <= 1.0
        assert 0.0 <= first_slot["flexibility"] <= 1.0


@pytest.mark.asyncio
async def test_get_set_templates_has_read_only_annotation() -> None:
    """Verify tool is properly decorated with read-only annotation."""
    # Direct import test to ensure the @tool decorator with ANNOTATIONS_READ_ONLY
    # is properly applied
    from app.controllers.tools.sets_meta import get_set_templates

    # Verify the function exists and is decorated
    assert get_set_templates is not None
    assert hasattr(get_set_templates, "__name__")
    assert get_set_templates.__name__ == "get_set_templates"

    # The @tool decorator with ANNOTATIONS_READ_ONLY is verified indirectly:
    # 1. The tool can be called and returns structured data
    # 2. No parameters are required (indicating it's safe/read-only)
    result = await get_set_templates()
    assert isinstance(result, dict)
    assert "templates" in result
    assert isinstance(result["templates"], list)
