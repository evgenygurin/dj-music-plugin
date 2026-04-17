"""unlock_namespace tool metadata tests."""

from __future__ import annotations

from app.v2.tools.admin import unlock_namespace as _mod


def test_tool_module_has_expected_symbols() -> None:
    assert hasattr(_mod, "unlock_namespace")
    assert hasattr(_mod, "NAMESPACES")
    assert hasattr(_mod, "NAMESPACE_TAGS")


def test_known_namespaces() -> None:
    assert "all" in _mod.NAMESPACES
    assert "sync" in _mod.NAMESPACES
    assert "crud:destructive" in _mod.NAMESPACES
    assert "provider:write" in _mod.NAMESPACES
