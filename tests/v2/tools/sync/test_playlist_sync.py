"""playlist_sync tool metadata tests.

Integration tests via Client(mcp).call_tool() require Phase 5 composition.
"""

from __future__ import annotations

from app.v2.tools.sync import playlist_sync as _mod


def test_tool_module_has_expected_symbols() -> None:
    assert hasattr(_mod, "playlist_sync")
    assert hasattr(_mod, "ConflictResolution")


def test_tool_importable() -> None:
    assert _mod.playlist_sync is not None
