"""Playlist repository with item management."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.playlist import Playlist, PlaylistItem
from app.repositories.base import BaseRepository


class PlaylistRepository(BaseRepository[Playlist]):
    """Repository for :class:`Playlist` with eager-loading and item helpers."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Playlist)

    async def get_with_items(self, playlist_id: int) -> Playlist | None:
        """Load a playlist with its items eagerly."""
        stmt = (
            select(Playlist)
            .where(Playlist.id == playlist_id)
            .options(selectinload(Playlist.items))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_track(self, playlist_id: int, track_id: int, position: int) -> PlaylistItem:
        """Add a track to a playlist at the given position (sort_index)."""
        item = PlaylistItem(
            playlist_id=playlist_id,
            track_id=track_id,
            sort_index=position,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def remove_track(self, playlist_id: int, position: int) -> bool:
        """Remove a playlist item by its sort_index. Returns ``True`` if found."""
        stmt = select(PlaylistItem).where(
            PlaylistItem.playlist_id == playlist_id,
            PlaylistItem.sort_index == position,
        )
        result = await self.session.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            return False
        await self.session.delete(item)
        await self.session.flush()
        return True
