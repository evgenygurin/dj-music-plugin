"""Playlist repository."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from app.v2.models.playlist import DjPlaylist, DjPlaylistItem
from app.v2.repositories.base import BaseRepository


class PlaylistRepository(BaseRepository[DjPlaylist]):
    model = DjPlaylist

    async def get_track_ids(self, playlist_id: int) -> list[int]:
        stmt = (
            select(DjPlaylistItem.track_id)
            .where(DjPlaylistItem.playlist_id == playlist_id)
            .order_by(DjPlaylistItem.sort_index)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def append_tracks(self, playlist_id: int, track_ids: list[int]) -> int:
        """Append tracks; returns new item count. Idempotent on duplicates."""
        start = (
            await self.session.scalar(
                select(func.coalesce(func.max(DjPlaylistItem.sort_index), -1)).where(
                    DjPlaylistItem.playlist_id == playlist_id
                )
            )
            or -1
        )
        items = [
            DjPlaylistItem(playlist_id=playlist_id, track_id=tid, sort_index=start + 1 + i)
            for i, tid in enumerate(track_ids)
        ]
        self.session.add_all(items)
        await self.session.flush()
        return len(items)

    async def remove_track(self, playlist_id: int, track_id: int) -> int:
        stmt = delete(DjPlaylistItem).where(
            DjPlaylistItem.playlist_id == playlist_id,
            DjPlaylistItem.track_id == track_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0  # type: ignore[attr-defined]
