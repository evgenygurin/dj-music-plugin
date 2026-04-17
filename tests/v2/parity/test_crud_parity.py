"""Migration-parity tests for CRUD tools.

These tests compare legacy ``manage_tracks`` / ``manage_playlists`` / ``manage_sets``
behaviour against new ``entity_create`` / ``entity_update`` / ``entity_delete``
tools. They are SKIPPED when legacy symbols are absent — which is the default
state until Phase 7 deletes legacy code.

Phase 5 integration (DbSessionMiddleware + FileSystemProvider) will enable
running these tests via ``Client(mcp).call_tool(...)``.
"""

from __future__ import annotations

import importlib.util

import pytest

LEGACY_AVAILABLE = (
    importlib.util.find_spec("app.controllers.tools.tracks") is not None
    and importlib.util.find_spec("app.controllers.tools.playlists") is not None
)


@pytest.mark.skipif(not LEGACY_AVAILABLE, reason="legacy tools not present")
def test_track_crud_parity_placeholder() -> None:
    """Legacy ``manage_tracks`` shape matches ``entity_create(entity='track')``.

    Placeholder: asserts the modules load side-by-side. Full parity requires
    Phase 5 FastMCP client fixture.
    """
    from app.controllers.tools import tracks as legacy

    assert hasattr(legacy, "manage_tracks") or hasattr(legacy, "create_track")


@pytest.mark.skipif(not LEGACY_AVAILABLE, reason="legacy tools not present")
def test_playlist_crud_parity_placeholder() -> None:
    from app.controllers.tools import playlists as legacy

    assert hasattr(legacy, "manage_playlist") or hasattr(legacy, "create_playlist")
