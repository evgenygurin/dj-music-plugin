"""Tests for app.server.surface — Phase 1 domain manager facade."""

from __future__ import annotations

import pytest

PHASE1_MANAGER_NAMES: frozenset[str] = frozenset(
    {
        "tracks_list",
        "tracks_get",
        "tracks_import",
        "tracks_analyze",
        "tracks_audio_download",
        "playlists_list",
        "playlists_sync",
        "sets_build",
        "sets_get",
        "library_aggregate",
        "transitions_score",
    }
)


def test_surface_module_importable() -> None:
    """Phase 1 ships app.server.surface with register_managers."""
    from app.server import surface

    assert hasattr(surface, "register_managers"), "register_managers missing"
    assert callable(surface.register_managers)


def test_manager_configs_exported() -> None:
    """Each Phase 1 manager has a ToolTransformConfig constant in module scope."""
    from app.server import surface

    expected_attrs = {name.upper() for name in PHASE1_MANAGER_NAMES}
    missing = expected_attrs - {a for a in dir(surface) if a.isupper()}
    assert not missing, f"missing ToolTransformConfig constants: {sorted(missing)}"
