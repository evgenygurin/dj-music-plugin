"""External ID mixin: platform ID lookups and local ID resolution."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.track import TrackExternalId


class ExternalIdMixin:
    """Mixin providing external platform ID operations.

    Expects ``self.session`` to be an :class:`AsyncSession` instance,
    set by :class:`TrackCoreRepository` via ``BaseRepository.__init__``.
    """

    session: AsyncSession

    async def get_external_id(
        self,
        track_id: int,
        platform: str,
    ) -> TrackExternalId | None:
        """Get external ID for a track on a specific platform."""
        stmt = select(TrackExternalId).where(
            TrackExternalId.track_id == track_id,
            TrackExternalId.platform == platform,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self,
        platform: str,
        external_id: str,
    ) -> TrackExternalId | None:
        """Find external ID record by platform and external ID."""
        stmt = select(TrackExternalId).where(
            TrackExternalId.platform == platform,
            TrackExternalId.external_id == external_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def add_external_id(
        self,
        track_id: int,
        platform: str,
        external_id: str,
    ) -> TrackExternalId:
        """Add an external ID mapping for a track."""
        ext = TrackExternalId(
            track_id=track_id,
            platform=platform,
            external_id=external_id,
        )
        self.session.add(ext)
        await self.session.flush()
        return ext

    async def resolve_local_ids_to_platform(
        self,
        local_ids: list[int],
    ) -> dict[int, str]:
        """Resolve local track IDs to external platform IDs.

        Returns mapping of local_track_id -> external_id string.
        """
        if not local_ids:
            return {}

        stmt = select(TrackExternalId.track_id, TrackExternalId.external_id).where(
            TrackExternalId.track_id.in_(local_ids),
            TrackExternalId.platform == "yandex_music",
        )
        result = await self.session.execute(stmt)
        return {row.track_id: row.external_id for row in result.all()}
