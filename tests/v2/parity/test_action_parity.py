"""Migration-parity tests for action tools (import/download/analyze/score/sync).

Skipped when legacy symbols are absent — default until Phase 7 cutover.
Phase 5 FastMCP client fixture will enable full round-trip comparisons.
"""

from __future__ import annotations

import importlib.util

import pytest


def _has(mod: str) -> bool:
    return importlib.util.find_spec(mod) is not None


LEGACY_IMPORT = _has("app.controllers.tools.import_download")
LEGACY_AUDIO = _has("app.controllers.tools.audio")
LEGACY_SETS = _has("app.controllers.tools.sets")
LEGACY_SYNC = _has("app.controllers.tools.sync")


@pytest.mark.skipif(not LEGACY_IMPORT, reason="legacy import_download tool absent")
def test_import_tracks_parity_placeholder() -> None:
    from app.controllers.tools import import_download as legacy

    assert hasattr(legacy, "import_tracks")


@pytest.mark.skipif(not LEGACY_AUDIO, reason="legacy audio tool absent")
def test_analyze_track_parity_placeholder() -> None:
    from app.controllers.tools import audio as legacy

    assert hasattr(legacy, "analyze_track")


@pytest.mark.skipif(not LEGACY_SETS, reason="legacy sets tool absent")
def test_score_transitions_parity_placeholder() -> None:
    from app.controllers.tools import sets as legacy

    assert hasattr(legacy, "score_transitions")


@pytest.mark.skipif(not LEGACY_SYNC, reason="legacy sync tool absent")
def test_sync_playlist_parity_placeholder() -> None:
    from app.controllers.tools import sync as legacy

    assert hasattr(legacy, "sync_playlist")
