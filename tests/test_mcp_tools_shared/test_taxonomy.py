"""Unit tests for the MCP tools taxonomy constants."""

from __future__ import annotations

import pytest

from app.mcp.tools._shared.taxonomy import (
    ANNOTATIONS_READ_ONLY,
    ANNOTATIONS_READ_ONLY_OPEN_WORLD,
    ANNOTATIONS_WRITE,
    ToolCategory,
    ToolTimeout,
)


def test_tool_category_values_match_legacy_tag_strings() -> None:
    """Tag strings are a stable wire format — do not rename accidentally."""
    assert ToolCategory.CORE.value == "core"
    assert ToolCategory.SETS.value == "sets"
    assert ToolCategory.DELIVERY.value == "delivery"
    assert ToolCategory.DISCOVERY.value == "discovery"
    assert ToolCategory.CURATION.value == "curation"
    assert ToolCategory.SYNC.value == "sync"
    assert ToolCategory.YM.value == "ym"
    assert ToolCategory.AUDIO.value == "audio"
    assert ToolCategory.ATOMIC.value == "atomic"
    assert ToolCategory.ADMIN.value == "admin"


def test_annotation_presets_are_immutable() -> None:
    """MappingProxyType should prevent accidental mutation."""
    with pytest.raises(TypeError):
        ANNOTATIONS_READ_ONLY["readOnlyHint"] = False  # type: ignore[index]
    with pytest.raises(TypeError):
        ANNOTATIONS_WRITE["readOnlyHint"] = True  # type: ignore[index]


def test_annotation_presets_content() -> None:
    assert ANNOTATIONS_READ_ONLY["readOnlyHint"] is True
    assert ANNOTATIONS_WRITE["readOnlyHint"] is False
    assert ANNOTATIONS_READ_ONLY_OPEN_WORLD["readOnlyHint"] is True
    assert ANNOTATIONS_READ_ONLY_OPEN_WORLD["openWorldHint"] is True


def test_timeouts_monotonic() -> None:
    assert ToolTimeout.MEDIUM < ToolTimeout.HEAVY < ToolTimeout.BATCH
