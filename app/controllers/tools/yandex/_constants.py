"""Shared constants and annotation presets for Yandex Music tools.

Kept private (underscore prefix) so the module is imported by the
tool submodules but not by anything outside the ``yandex`` package.
"""

from __future__ import annotations

from typing import Any, Final

YM_WRITE_ANNOTATIONS: Final[dict[str, Any]] = {
    "readOnlyHint": False,
    "openWorldHint": True,
}

MAX_BATCH_TRACKS: Final[int] = 100
MAX_SEARCH_LIMIT: Final[int] = 20
MAX_LIKED_PAGE: Final[int] = 200
MAX_PLAYLIST_TRACKS_PAGE: Final[int] = 200
