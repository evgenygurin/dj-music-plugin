"""Playlist domain schemas."""

from __future__ import annotations

from dj_music.schemas.base import BaseEntity


class Playlist(BaseEntity):
    """Playlist entity."""

    name: str = ""
    parent_id: int | None = None
    source_app: str | None = None
    source_of_truth: str = "local"
    platform_ids: str | None = None  # JSON mapping


class PlaylistItem(BaseEntity):
    """A track reference within a playlist."""

    playlist_id: int = 0
    track_id: int = 0
    sort_index: int = 0
    # TODO: add remaining fields (added_at) during Phase 4
