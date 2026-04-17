"""Track repository — inherits BaseRepository CRUD + 4 domain methods."""

from __future__ import annotations

from sqlalchemy import select

from app.models.track import Track, TrackExternalId
from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.base import BaseRepository


class TrackRepository(BaseRepository[Track]):
    model = Track

    async def get_provider_id(self, track_id: int, provider_code: str) -> str | None:
        """Return ``external_id`` for ``track_id`` on ``provider_code`` or None."""
        stmt = select(TrackExternalId.external_id).where(
            TrackExternalId.track_id == track_id,
            TrackExternalId.provider_code == provider_code,
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def batch_get_by_provider_ids(
        self, provider_code: str, external_ids: list[str]
    ) -> dict[str, Track]:
        """Resolve many ``external_id`` values → Track instances in one query."""
        if not external_ids:
            return {}
        stmt = (
            select(TrackExternalId.external_id, Track)
            .join(Track, Track.id == TrackExternalId.track_id)
            .where(
                TrackExternalId.provider_code == provider_code,
                TrackExternalId.external_id.in_(external_ids),
            )
        )
        rows = (await self.session.execute(stmt)).all()
        return {ext_id: track for ext_id, track in rows}

    async def get_unanalyzed(self, level: int, limit: int = 100) -> list[int]:
        """Return track IDs whose analysis_level < ``level`` (or no features row)."""
        stmt = (
            select(Track.id)
            .outerjoin(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )
            .where(
                (TrackAudioFeaturesComputed.track_id.is_(None))
                | (TrackAudioFeaturesComputed.analysis_level < level)
            )
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars())

    async def ensure_external_id(
        self, track_id: int, provider_code: str, external_id: str
    ) -> TrackExternalId:
        """Upsert one (track_id, provider_code, external_id) mapping."""
        existing = await self.session.scalar(
            select(TrackExternalId).where(
                TrackExternalId.track_id == track_id,
                TrackExternalId.provider_code == provider_code,
            )
        )
        if existing is not None:
            if existing.external_id != external_id:
                existing.external_id = external_id
                await self.session.flush()
            return existing
        row = TrackExternalId(
            track_id=track_id, provider_code=provider_code, external_id=external_id
        )
        self.session.add(row)
        await self.session.flush()
        return row
