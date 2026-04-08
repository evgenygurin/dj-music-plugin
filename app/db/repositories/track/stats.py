"""Stats mixin: library dashboard counts and platform coverage."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audio import TrackAudioFeaturesComputed
from app.db.models.track import Track, TrackExternalId


class StatsMixin:
    """Mixin providing library statistics and platform count queries.

    Expects ``self.session`` to be an :class:`AsyncSession` instance,
    set by :class:`TrackCoreRepository` via ``BaseRepository.__init__``.
    """

    session: AsyncSession

    async def get_library_stats(self) -> dict[str, Any]:
        """Library dashboard: counts, coverage, distributions."""
        from app.db.models.playlist import Playlist
        from app.db.models.set import DjSet

        total_tracks = (await self.session.execute(select(func.count(Track.id)))).scalar() or 0
        active_tracks = (
            await self.session.execute(select(func.count(Track.id)).where(Track.status == 0))
        ).scalar() or 0
        archived_tracks = (
            await self.session.execute(select(func.count(Track.id)).where(Track.status == 1))
        ).scalar() or 0
        # Only count features for active tracks — otherwise an
        # archived-track-with-features inflates the numerator and breaks
        # the invariant ``with_features + without_features == active``.
        tracks_with_features = (
            await self.session.execute(
                select(func.count(TrackAudioFeaturesComputed.track_id))
                .join(Track, Track.id == TrackAudioFeaturesComputed.track_id)
                .where(Track.status == 0)
            )
        ).scalar() or 0
        playlist_count = (
            await self.session.execute(select(func.count(Playlist.id)))
        ).scalar() or 0
        set_count = (await self.session.execute(select(func.count(DjSet.id)))).scalar() or 0

        bpm_ranges: dict[str, int] = {}
        if tracks_with_features > 0:
            stmt_bpm = select(TrackAudioFeaturesComputed.bpm).where(
                TrackAudioFeaturesComputed.bpm.isnot(None)
            )
            result = await self.session.execute(stmt_bpm)
            for (bpm,) in result.all():
                if bpm is not None:
                    bucket = f"{int(bpm // 10) * 10}-{int(bpm // 10) * 10 + 9}"
                    bpm_ranges[bucket] = bpm_ranges.get(bucket, 0) + 1

        ym_linked = (
            await self.session.execute(
                select(func.count(TrackExternalId.id)).where(
                    TrackExternalId.platform == "yandex_music"
                )
            )
        ).scalar() or 0

        return {
            "tracks": {
                "total": total_tracks,
                "active": active_tracks,
                "archived": archived_tracks,
                "with_features": tracks_with_features,
                "without_features": active_tracks - tracks_with_features,
                "feature_coverage": (
                    round(tracks_with_features / active_tracks * 100, 1)
                    if active_tracks > 0
                    else 0.0
                ),
            },
            "playlists": playlist_count,
            "sets": set_count,
            "ym_linked_tracks": ym_linked,
            "bpm_distribution": dict(sorted(bpm_ranges.items())),
        }

    async def get_platform_counts(self) -> dict[str, int]:
        """Return count of tracks linked per platform."""
        stmt = select(
            TrackExternalId.platform,
            func.count(TrackExternalId.id).label("track_count"),
        ).group_by(TrackExternalId.platform)
        result = await self.session.execute(stmt)
        return {row.platform: row.track_count for row in result.all()}
