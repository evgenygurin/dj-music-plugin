"""Unit tests for the MCP tools taxonomy constants."""

from __future__ import annotations

from app.controllers.tools._shared.taxonomy import (
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
    assert ToolCategory.MEMORY.value == "memory"
    assert ToolCategory.ADMIN.value == "admin"


def test_annotation_presets_content() -> None:
    """Presets hold the exact MCP annotation flags tools rely on."""
    assert ANNOTATIONS_READ_ONLY == {"readOnlyHint": True, "idempotentHint": True}
    assert ANNOTATIONS_WRITE == {"readOnlyHint": False}
    assert ANNOTATIONS_READ_ONLY_OPEN_WORLD == {
        "readOnlyHint": True,
        "idempotentHint": True,
        "openWorldHint": True,
    }


def test_annotation_presets_are_distinct_instances() -> None:
    """Each preset is a separate dict so mutating one does not leak."""
    assert ANNOTATIONS_READ_ONLY is not ANNOTATIONS_WRITE
    assert ANNOTATIONS_READ_ONLY is not ANNOTATIONS_READ_ONLY_OPEN_WORLD


def test_timeouts_monotonic() -> None:
    assert ToolTimeout.MEDIUM < ToolTimeout.HEAVY < ToolTimeout.BATCH
