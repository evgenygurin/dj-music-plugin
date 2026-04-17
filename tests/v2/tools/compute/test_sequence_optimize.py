"""sequence_optimize tool metadata tests.

Integration tests via Client(mcp).call_tool() require Phase 5 composition;
here we assert decorator-level metadata only.
"""

from __future__ import annotations

from app.v2.tools.compute import sequence_optimize as _mod


def test_tool_module_has_expected_symbols() -> None:
    assert hasattr(_mod, "sequence_optimize")


def test_tool_importable() -> None:
    # Ensures the decorator chain executed without errors at import time.
    assert _mod.sequence_optimize is not None
