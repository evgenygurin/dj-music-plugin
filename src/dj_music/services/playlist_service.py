"""Playlist service — business logic for playlist CRUD and track management.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from dj_music.core.errors import NotFoundError, ValidationError
from dj_music.core.utils.pagination import CursorPage
from dj_music.models.playlist import Playlist
from dj_music.repositories.playlist import PlaylistRepository
from dj_music.schemas import PlaylistSummary


class PlaylistService:
    """Business logic for playlists: CRUD, add/remove tracks."""

    def __init__(self, repo: PlaylistRepository) -> None:
        self._repo = repo

    # ── Read ─────────────────────────────────────────

    async def get_by_id(self, playlist_id: int) -> Playlist:
        playlist = await self._repo.get_with_items(playlist_id)
        if playlist is None:
            raise NotFoundError("Playlist", playlist_id)
        return playlist

    async def search_by_name(self, query: str) -> Playlist | None:
        """Find first playlist by name (case-insensitive ILIKE), with items."""
        return await self._repo.search_with_items(query)

    async def reorder_tracks(
        self,
        playlist_id: int,
        track_ids: list[int],
        positions: list[int],
    ) -> Playlist:
        """Replace all playlist items with a new ordering."""
        await self.get_by_id(playlist_id)  # validate playlist exists
        await self._repo.clear_items(playlist_id)
        for tid, pos in zip(track_ids, positions, strict=False):
            await self._repo.add_track(playlist_id, tid, pos)
        return await self.get_by_id(playlist_id)

    async def list_all(
        self, *, limit: int = 20, cursor: str | None = None, source: str | None = None
    ) -> CursorPage[Playlist]:
        return await self._repo.list_with_items(source=source, limit=limit, cursor=cursor)

    # ── Write ────────────────────────────────────────

    async def create(self, name: str, source_of_truth: str = "local") -> Playlist:
        if not name:
            raise ValidationError("name is required")
        playlist = Playlist(name=name, source_of_truth=source_of_truth)
        return await self._repo.create(playlist)

    async def update(self, playlist_id: int, **fields) -> Playlist:  # type: ignore[no-untyped-def]
        import json

        playlist = await self.get_by_id(playlist_id)
        for key, value in fields.items():
            if hasattr(playlist, key):
                # Serialize dict/list to JSON for Text columns (e.g. platform_ids)
                if isinstance(value, dict | list):
                    value = json.dumps(value)
                setattr(playlist, key, value)
        return await self._repo.update(playlist)

    async def delete(self, playlist_id: int) -> bool:
        return await self._repo.delete(playlist_id)

    async def add_tracks(self, playlist_id: int, track_ids: list[int]) -> int:
        """Add tracks to playlist. Returns new track count."""
        playlist = await self.get_by_id(playlist_id)
        max_idx = max((item.sort_index for item in playlist.items), default=-1)
        for i, tid in enumerate(track_ids):
            await self._repo.add_track(playlist_id, tid, max_idx + 1 + i)

        return await self._repo.count_items(playlist_id)

    async def remove_track(self, playlist_id: int, position: int) -> bool:
        return await self._repo.remove_track(playlist_id, position)

    # ── Converters ───────────────────────────────────

    @staticmethod
    def to_summary(playlist: Playlist, track_count: int | None = None) -> PlaylistSummary:
        if track_count is None:
            try:
                track_count = len(playlist.items) if playlist.items else 0
            except Exception:
                track_count = 0
        return PlaylistSummary(
            id=playlist.id,
            name=playlist.name,
            track_count=track_count,
            source_of_truth=playlist.source_of_truth,
        )
