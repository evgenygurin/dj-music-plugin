"""Track repository with text search and feature-based filtering."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import CursorPage
from app.models.audio import TrackAudioFeaturesComputed
from app.models.library import DjLibraryItem
from app.models.platform import YandexMetadata
from app.models.track import Artist, Track, TrackExternalId
from app.repositories.base import BaseRepository


class TrackRepository(BaseRepository[Track]):
    """Repository for :class:`Track` with search and filtering helpers."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Track)

    async def get_by_title(self, title: str) -> Track | None:
        """Find active track by exact title match."""
        stmt = select(Track).where(Track.title == title, Track.status == 0)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_text(self, query: str, limit: int = 10) -> list[Track]:
        """Case-insensitive search on track title using ILIKE."""
        pattern = f"%{query}%"
        stmt = select(Track).where(Track.title.ilike(pattern)).order_by(Track.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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

        return await self._paginate(stmt, limit=limit, cursor=cursor)

    async def search_artists(self, query: str, limit: int = 10) -> list[Artist]:
        """Case-insensitive search on artist name."""
        pattern = f"%{query}%"
        stmt = select(Artist).where(Artist.name.ilike(pattern)).order_by(Artist.id).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_active_track_ids(self) -> list[int]:
        """Return IDs of all active tracks."""
        stmt = select(Track.id).where(Track.status == 0)
        result = await self.session.execute(stmt)
        return [r[0] for r in result.all()]

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
        await self.add_external_id(track.id, platform, external_id)
        return track

    async def get_ym_metadata(self, track_id: int) -> YandexMetadata | None:
        """Get Yandex Music metadata for a track."""
        stmt = select(YandexMetadata).where(YandexMetadata.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_ym_metadata(
        self,
        track_id: int,
        ym_id: str,
        ym_track: Any,
    ) -> YandexMetadata:
        """Save YM metadata for a track from a YM API response object."""
        albums = getattr(ym_track, "albums", None) or []
        album = albums[0] if albums else {}
        meta = YandexMetadata(
            track_id=track_id,
            yandex_track_id=ym_id,
            album_id=str(album.get("id", "")) if album else None,
            album_title=album.get("title") if album else None,
            album_genre=album.get("genre") if album else None,
            album_year=album.get("year") if album else None,
            duration_ms=getattr(ym_track, "duration_ms", None),
            cover_uri=getattr(ym_track, "cover_uri", None),
            explicit=getattr(ym_track, "explicit", None),
        )
        self.session.add(meta)
        await self.session.flush()
        return meta

    async def get_artist_names(self, track_id: int) -> str | None:
        """Get comma-separated artist names for a track."""
        from app.models.track import TrackArtist

        stmt = select(TrackArtist).where(TrackArtist.track_id == track_id)
        result = await self.session.execute(stmt)
        artists = list(result.scalars().all())
        if not artists:
            return None
        return (
            ", ".join(a.artist.name for a in artists if hasattr(a, "artist") and a.artist) or None
        )

    async def get_library_file_path(self, track_id: int) -> str | None:
        """Get the file path from DjLibraryItem for a track."""
        stmt = select(DjLibraryItem.file_path).where(DjLibraryItem.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_library_item(self, track_id: int) -> DjLibraryItem | None:
        """Get DjLibraryItem for a track."""
        stmt = select(DjLibraryItem).where(DjLibraryItem.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_library_item(self, item: DjLibraryItem) -> DjLibraryItem:
        """Persist a DjLibraryItem."""
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_library_stats(self) -> dict[str, Any]:
        """Library dashboard: counts, coverage, distributions."""
        from sqlalchemy import func

        from app.models.playlist import Playlist
        from app.models.set import DjSet

        total_tracks = (await self.session.execute(select(func.count(Track.id)))).scalar() or 0
        active_tracks = (
            await self.session.execute(select(func.count(Track.id)).where(Track.status == 0))
        ).scalar() or 0
        archived_tracks = (
            await self.session.execute(select(func.count(Track.id)).where(Track.status == 1))
        ).scalar() or 0
        tracks_with_features = (
            await self.session.execute(select(func.count(TrackAudioFeaturesComputed.track_id)))
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

        from app.core.pagination import decode_cursor, encode_cursor
        from app.models.set import SetItem, SetVersion

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
        order_col = sort_map.get(sort_by, TrackAudioFeaturesComputed.bpm)
        stmt = stmt.order_by(order_col)

        count_stmt = select(sa_func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        if cursor is not None:
            last_id = decode_cursor(cursor)
            stmt = stmt.where(Track.id > last_id)

        stmt = stmt.order_by(Track.id).limit(limit)
        result = await self.session.execute(stmt)
        tracks = list(result.scalars().all())

        next_cursor_val: str | None = None
        if tracks and len(tracks) == limit:
            next_cursor_val = encode_cursor(tracks[-1].id)

        return CursorPage(items=tracks, next_cursor=next_cursor_val, total=total)

    async def get_platform_counts(self) -> dict[str, int]:
        """Return count of tracks linked per platform."""
        stmt = select(
            TrackExternalId.platform,
            func.count(TrackExternalId.id).label("track_count"),
        ).group_by(TrackExternalId.platform)
        result = await self.session.execute(stmt)
        return {row.platform: row.track_count for row in result.all()}
