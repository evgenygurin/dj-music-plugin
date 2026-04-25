"""Track features repository — batch load for scoring + targeted mood writes."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select, update

from app.models.track_features import TrackAudioFeaturesComputed
from app.repositories.base import BaseRepository
from app.shared.errors import NotFoundError
from app.shared.features import TrackFeatures


class TrackFeaturesRepository(BaseRepository[TrackAudioFeaturesComputed]):
    model = TrackAudioFeaturesComputed

    async def get_by_track_id(self, track_id: int) -> TrackAudioFeaturesComputed | None:
        """Return the features row for ``track_id`` (primary key), or None."""
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        return await self.session.scalar(stmt)  # type: ignore[no-any-return]

    async def upsert(self, *, track_id: int, **values: Any) -> TrackAudioFeaturesComputed:
        """INSERT or UPDATE the features row for ``track_id``.

        Used by the analyze handler after pipeline completion. Only whitelists
        columns that exist on the model to tolerate pipeline extras.
        """
        allowed = {c.key for c in TrackAudioFeaturesComputed.__table__.columns}
        clean = {k: v for k, v in values.items() if k in allowed and k != "track_id"}
        existing = await self.get_by_track_id(track_id)
        if existing is not None:
            for key, val in clean.items():
                setattr(existing, key, val)
            await self.session.flush()
            return existing
        row = TrackAudioFeaturesComputed(track_id=track_id, **clean)
        self.session.add(row)
        await self.session.flush()
        return row

    async def get_scoring_features_batch(self, track_ids: list[int]) -> dict[int, TrackFeatures]:
        """Batch load scoring features as TrackFeatures dataclasses (JSON vectors parsed)."""
        if not track_ids:
            return {}
        stmt = select(TrackAudioFeaturesComputed).where(
            TrackAudioFeaturesComputed.track_id.in_(track_ids)
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return {r.track_id: TrackFeatures.from_db(r) for r in rows}

    async def set_mood(self, track_id: int, *, mood: str, confidence: float) -> None:
        """Update mood + confidence on an existing features row."""
        stmt = (
            update(TrackAudioFeaturesComputed)
            .where(TrackAudioFeaturesComputed.track_id == track_id)
            .values(mood=mood, mood_confidence=confidence)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:  # type: ignore[attr-defined]
            raise NotFoundError("track_features", track_id)
        await self.session.flush()

    async def get_analysis_level(self, track_id: int) -> int:
        """Return current analysis_level (0 if no row)."""
        stmt = select(TrackAudioFeaturesComputed.analysis_level).where(
            TrackAudioFeaturesComputed.track_id == track_id
        )
        row = await self.session.scalar(stmt)
        return int(row) if row is not None else 0
