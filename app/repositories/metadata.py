"""Metadata repository — generic entity resolution for normalization.

Provides _get_or_create and _link_if_not_exists patterns used by MetadataService
to normalize YM data into Artist/Genre/Label/Release entities.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import YandexMetadata
from app.models.track import Release, Track


class MetadataRepository:
    """Data access for metadata normalization operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ym_metadata(self, track_id: int) -> YandexMetadata | None:
        """Get YandexMetadata row for a track."""
        stmt = select(YandexMetadata).where(YandexMetadata.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_track_title(self, track_id: int) -> str | None:
        """Get track title by ID."""
        stmt = select(Track.title).where(Track.id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_track(self, track_id: int) -> Track | None:
        """Get track by ID."""
        stmt = select(Track).where(Track.id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_playlist_track_ids(self, playlist_id: int) -> list[int]:
        """Get ordered track IDs for a playlist."""
        from app.models.playlist import PlaylistItem

        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        result = await self.session.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_or_create(self, model_class: type, **match_fields: Any) -> Any:
        """Get existing entity by fields, or create new one."""
        stmt: Any = select(model_class)
        for col, val in match_fields.items():
            stmt = stmt.where(getattr(model_class, col) == val)
        result = await self.session.execute(stmt.limit(1))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        instance = model_class(**match_fields)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def link_if_not_exists(self, junction_model: type, **fields: Any) -> bool:
        """Create junction row if it doesn't exist. Returns True if created."""
        stmt: Any = select(junction_model)
        for col, val in fields.items():
            stmt = stmt.where(getattr(junction_model, col) == val)
        result = await self.session.execute(stmt.limit(1))
        if result.scalar_one_or_none() is not None:
            return False
        self.session.add(junction_model(**fields))
        await self.session.flush()
        return True

    async def find_release(
        self,
        title: str,
        release_date: Any | None = None,
    ) -> Release | None:
        """Find a release by title and optional release_date."""
        stmt = select(Release).where(Release.title == title)
        if release_date is not None:
            stmt = stmt.where(Release.release_date == release_date)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_release(self, **fields: Any) -> Release:
        """Create a Release row."""
        release = Release(**fields)
        self.session.add(release)
        await self.session.flush()
        return release

    async def update_track_title(self, track_id: int, new_title: str) -> bool:
        """Update a track's title. Returns True if updated."""
        track = await self.get_track(track_id)
        if track is None:
            return False
        track.title = new_title
        await self.session.flush()
        return True
