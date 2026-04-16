"""Library mixin: file path, DjLibraryItem, and Yandex Music metadata."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.library import DjLibraryItem
from app.db.models.platform import YandexMetadata


class LibraryMixin:
    """Mixin providing DJ library file and YM metadata operations.

    Expects ``self.session`` to be an :class:`AsyncSession` instance,
    set by :class:`TrackCoreRepository` via ``BaseRepository.__init__``.
    """

    session: AsyncSession

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

    async def get_platform_metadata(self, track_id: int) -> YandexMetadata | None:
        """Get Yandex Music metadata for a track."""
        stmt = select(YandexMetadata).where(YandexMetadata.track_id == track_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def save_platform_metadata(
        self,
        track_id: int,
        ym_id: str,
        ym_track: Any,
    ) -> YandexMetadata:
        """Save platform metadata from either a ProviderTrack or a YMTrack response object."""
        if hasattr(ym_track, "album_id"):
            # ProviderTrack — scalar album fields
            meta = YandexMetadata(
                track_id=track_id,
                yandex_track_id=ym_id,
                album_id=str(ym_track.album_id) if ym_track.album_id else None,
                album_title=getattr(ym_track, "album_title", None),
                album_genre=getattr(ym_track, "album_genre", None),
                duration_ms=getattr(ym_track, "duration_ms", None),
                cover_uri=getattr(ym_track, "cover_url", None),
                explicit=getattr(ym_track, "explicit", None),
            )
        else:
            # YMTrack — dict-style albums list
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
