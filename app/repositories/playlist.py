"""Playlist repository with item management."""

from sqlalchemy import delete, func, select
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

    async def get_track_ids(self, playlist_id: int) -> list[int]:
        """Return ordered track IDs for a playlist.

        Commonly used by tools to get the track pool for scoring,
        classification, and set building.
        """
        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]

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

    async def search_by_name(self, query: str, limit: int = 10) -> list[Playlist]:
        """Search playlists by name (case-insensitive)."""
        stmt = (
            select(Playlist)
            .where(Playlist.name.ilike(f"%{query}%"))
            .order_by(Playlist.id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_with_items(self, query: str) -> Playlist | None:
        """Find first playlist matching name query, with items eager-loaded."""
        stmt = (
            select(Playlist)
            .where(Playlist.name.ilike(f"%{query}%"))
            .options(selectinload(Playlist.items))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_by_name(self, name: str) -> tuple[Playlist, bool]:
        """Return existing playlist by exact name, or create a new one.

        Returns:
            Tuple of (playlist, created) where created is True if a new
            playlist was created.
        """
        stmt = select(Playlist).where(Playlist.name == name).limit(1)
        result = await self.session.execute(stmt)
        playlist = result.scalar_one_or_none()
        if playlist is not None:
            return playlist, False
        playlist = Playlist(name=name)
        self.session.add(playlist)
        await self.session.flush()
        return playlist, True

    async def clear_items(self, playlist_id: int) -> int:
        """Remove all items from a playlist. Returns count deleted."""
        stmt = delete(PlaylistItem).where(PlaylistItem.playlist_id == playlist_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount  # type: ignore[return-value]

    async def get_max_sort_index(self, playlist_id: int) -> int:
        """Return the highest sort_index in a playlist, or -1 if empty."""
        stmt = select(func.max(PlaylistItem.sort_index)).where(
            PlaylistItem.playlist_id == playlist_id
        )
        result = await self.session.execute(stmt)
        val = result.scalar_one_or_none()
        return val if val is not None else -1
