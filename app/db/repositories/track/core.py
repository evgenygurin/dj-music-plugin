"""Core track repository: CRUD, search, and artist helpers."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.track import Artist, Track, TrackArtist
from app.db.repositories.base import BaseRepository


class TrackCoreRepository(BaseRepository[Track]):
    """Repository for :class:`Track` with search and artist helpers.

    Inherits CRUD operations and cursor pagination from :class:`BaseRepository`.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Track)

    async def get_by_title(self, title: str) -> Track | None:
        """Find active track by exact title match."""
        stmt = select(Track).where(Track.title == title, Track.status == 0)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_text(self, query: str, limit: int = 10) -> list[Track]:
        """Case-insensitive search across track title and linked artist names."""
        from sqlalchemy import or_

        pattern = f"%{query}%"
        stmt = (
            select(Track)
            .outerjoin(TrackArtist, TrackArtist.track_id == Track.id)
            .outerjoin(Artist, Artist.id == TrackArtist.artist_id)
            .where(or_(Track.title.ilike(pattern), Artist.name.ilike(pattern)))
            .distinct()
            .order_by(Track.id)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, ids: list[int]) -> dict[int, Track]:
        """Fetch multiple tracks by IDs in a single query.

        Returns mapping of track_id → Track.
        """
        if not ids:
            return {}
        stmt = select(Track).where(Track.id.in_(ids))
        result = await self.session.execute(stmt)
        return {t.id: t for t in result.scalars().all()}

    async def get_active_track_ids(self) -> list[int]:
        """Return IDs of all active tracks."""
        stmt = select(Track.id).where(Track.status == 0)
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]

    async def search_artists(self, query: str, limit: int = 10) -> list[Artist]:
        """Case-insensitive search on artist name."""
        pattern = f"%{query}%"
        stmt = select(Artist).where(Artist.name.ilike(pattern)).order_by(Artist.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_artist_names(self, track_id: int) -> str | None:
        """Get comma-separated artist names for a track."""

        stmt = (
            select(Artist.name)
            .join(TrackArtist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id == track_id)
        )
        result = await self.session.execute(stmt)
        names = [row[0] for row in result.all()]
        return ", ".join(names) if names else None

    async def get_artist_names_batch(self, track_ids: list[int]) -> dict[int, list[str]]:
        """Get artist names for multiple tracks in a single query.

        Returns mapping of track_id → list of artist names.
        """
        if not track_ids:
            return {}

        stmt = (
            select(TrackArtist.track_id, Artist.name)
            .join(Artist, TrackArtist.artist_id == Artist.id)
            .where(TrackArtist.track_id.in_(track_ids))
            .order_by(TrackArtist.track_id)
        )
        result = await self.session.execute(stmt)

        names_map: dict[int, list[str]] = {}
        for track_id, name in result.all():
            names_map.setdefault(track_id, []).append(name)
        return names_map

    async def create_with_external_id(
        self,
        title: str,
        duration_ms: int | None = None,
        platform: str = "yandex_music",
        external_id: str = "",
    ) -> Track:
        """Create a track and link an external ID in one step."""
        track = Track(title=title, status=0, duration_ms=duration_ms)
        track = await self.create(track)
        await self.add_external_id(track.id, platform, external_id)  # type: ignore[attr-defined]
        return track
