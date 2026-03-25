"""Playlist service — business logic for playlist CRUD and track management.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.core.errors import NotFoundError, ValidationError
from app.core.pagination import CursorPage
from app.core.schemas import PlaylistSummary
from app.models.playlist import Playlist, PlaylistItem
from app.repositories.playlist import PlaylistRepository


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

    async def list_all(
        self, *, limit: int = 20, cursor: str | None = None, source: str | None = None
    ) -> CursorPage[Playlist]:
        from sqlalchemy.orm import selectinload

        stmt = select(Playlist).options(selectinload(Playlist.items))
        if source is not None:
            stmt = stmt.where(Playlist.source_of_truth == source)
        return await self._repo._paginate(stmt, limit=limit, cursor=cursor)

    # ── Write ────────────────────────────────────────

    async def create(self, name: str, source_of_truth: str = "local") -> Playlist:
        if not name:
            raise ValidationError("name is required")
        playlist = Playlist(name=name, source_of_truth=source_of_truth)
        return await self._repo.create(playlist)

    async def update(self, playlist_id: int, **fields) -> Playlist:  # type: ignore[no-untyped-def]
        playlist = await self.get_by_id(playlist_id)
        for key, value in fields.items():
            if hasattr(playlist, key):
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

        # Count directly to avoid stale cache
        count_stmt = (
            select(func.count())
            .select_from(PlaylistItem)
            .where(PlaylistItem.playlist_id == playlist_id)
        )
        result = await self._repo.session.execute(count_stmt)
        return result.scalar() or 0

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
