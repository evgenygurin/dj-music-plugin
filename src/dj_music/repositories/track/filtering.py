"""Filtering mixin: parametric feature filters for track discovery."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dj_music.core.utils.pagination import CursorPage
from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track


class FilteringMixin:
    """Mixin providing parametric audio-feature filtering for tracks.

    Expects ``self.session`` to be an :class:`AsyncSession` instance and
    ``self._paginate()`` from :class:`BaseRepository`, both provided by
    :class:`TrackCoreRepository` via ``BaseRepository.__init__``.
    """

    session: AsyncSession

    async def filter_by_features(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key_code: int | None = None,
        energy_min: float | None = None,
        energy_max: float | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[Track]:
        """Filter tracks by joining with audio features for parametric queries."""
        stmt = select(Track).join(
            TrackAudioFeaturesComputed,
            TrackAudioFeaturesComputed.track_id == Track.id,
        )

        if bpm_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm >= bpm_min)
        if bpm_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm <= bpm_max)
        if key_code is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.key_code == key_code)
        if energy_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean >= energy_min)
        if energy_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean <= energy_max)

        return await self._paginate(stmt, limit=limit, cursor=cursor)  # type: ignore[attr-defined,no-any-return]

    async def filter_tracks_advanced(
        self,
        *,
        bpm_min: float | None = None,
        bpm_max: float | None = None,
        key_code: int | None = None,
        compatible_key_codes: list[int] | None = None,
        energy_min: float | None = None,
        energy_max: float | None = None,
        has_features: bool | None = None,
        exclude_set_id: int | None = None,
        sort_by: str = "bpm",
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[Track]:
        """Advanced parametric track filter used by SearchService."""
        from sqlalchemy import func as sa_func

        from dj_music.core.utils.pagination import decode_cursor, encode_cursor
        from app.db.models.set import SetItem, SetVersion

        if has_features is False:
            stmt = (
                select(Track)
                .outerjoin(
                    TrackAudioFeaturesComputed,
                    TrackAudioFeaturesComputed.track_id == Track.id,
                )
                .where(TrackAudioFeaturesComputed.track_id.is_(None))
            )
        else:
            stmt = select(Track).join(
                TrackAudioFeaturesComputed,
                TrackAudioFeaturesComputed.track_id == Track.id,
            )

        if bpm_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm >= bpm_min)
        if bpm_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.bpm <= bpm_max)
        if key_code is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.key_code == key_code)
        if compatible_key_codes is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.key_code.in_(compatible_key_codes))
        if energy_min is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean >= energy_min)
        if energy_max is not None:
            stmt = stmt.where(TrackAudioFeaturesComputed.energy_mean <= energy_max)
        if exclude_set_id is not None:
            latest_version = (
                select(SetVersion.id)
                .where(SetVersion.set_id == exclude_set_id)
                .order_by(SetVersion.id.desc())
                .limit(1)
                .scalar_subquery()
            )
            existing_track_ids = select(SetItem.track_id).where(
                SetItem.version_id == latest_version
            )
            stmt = stmt.where(Track.id.not_in(existing_track_ids))

        sort_map = {
            "bpm": TrackAudioFeaturesComputed.bpm,
            "energy": TrackAudioFeaturesComputed.energy_mean,
            "title": Track.title,
            "id": Track.id,
        }
        # Parse direction suffix: "id_desc" → ("id", desc), "bpm" → ("bpm", asc)
        descending = False
        sort_key = sort_by
        if sort_by.endswith("_desc"):
            sort_key = sort_by[: -len("_desc")]
            descending = True
        elif sort_by.endswith("_asc"):
            sort_key = sort_by[: -len("_asc")]
        order_col = sort_map.get(sort_key, TrackAudioFeaturesComputed.bpm)
        primary = order_col.desc() if descending else order_col

        count_stmt = select(sa_func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        if cursor is not None:
            last_id = decode_cursor(cursor)
            stmt = stmt.where(Track.id > last_id)

        # Combined order_by: primary sort + Track.id for stable pagination.
        # TODO: cursor pagination uses Track.id > last_id which only works correctly
        # when primary sort is by Track.id. For non-ID sorts, keyset pagination
        # would be needed for fully correct cursor behavior.
        stmt = stmt.order_by(primary, Track.id).limit(limit)
        result = await self.session.execute(stmt)
        tracks = list(result.scalars().all())

        next_cursor_val: str | None = None
        if tracks and len(tracks) == limit:
            next_cursor_val = encode_cursor(tracks[-1].id)

        return CursorPage(items=tracks, next_cursor=next_cursor_val, total=total)
