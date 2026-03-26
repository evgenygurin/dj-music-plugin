"""Metadata normalization service — parse YM data into Artist/Genre/Label/Release entities.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.platform import YandexMetadata
from app.models.track import (
    Artist,
    Genre,
    Label,
    Release,
    Track,
    TrackArtist,
    TrackGenre,
    TrackLabel,
    TrackRelease,
)

logger = logging.getLogger(__name__)


class MetadataService:
    """Normalize YM metadata into proper Artist/Genre/Label/Release entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Public API ───────────────────────────────────────

    async def normalize_track_metadata(
        self,
        track_id: int,
        ym_track: Any | None = None,
    ) -> dict[str, Any]:
        """Parse YM metadata for a track and create/link artists, genres, labels, releases.

        Args:
            track_id: Local track ID.
            ym_track: Optional YMTrack API response object. If not provided,
                      falls back to data stored in YandexMetadata table.

        Returns:
            Summary dict with counts of created/linked entities.
        """
        artists_linked = 0
        genres_linked = 0
        labels_linked = 0
        releases_linked = 0

        # Extract raw data from YMTrack or fall back to YandexMetadata
        raw = await self._extract_raw_data(track_id, ym_track)
        if raw is None:
            return {
                "track_id": track_id,
                "artists": 0,
                "genres": 0,
                "labels": 0,
                "releases": 0,
                "title_cleaned": False,
            }

        # 1. Artists
        for artist_info in raw["artists"]:
            name = artist_info.get("name", "").strip()
            if not name:
                continue
            artist = await self._get_or_create_artist(name)
            role = artist_info.get("role", "primary")
            if await self._link_track_artist(track_id, artist.id, role):
                artists_linked += 1

        # 2. Genre
        genre_name = raw.get("genre")
        if genre_name and genre_name.strip():
            genre = await self._get_or_create_genre(genre_name.strip())
            if await self._link_track_genre(track_id, genre.id):
                genres_linked += 1

        # 3. Label
        label_name = raw.get("label")
        label_obj: Label | None = None
        if label_name and label_name.strip():
            label_obj = await self._get_or_create_label(label_name.strip())
            if await self._link_track_label(track_id, label_obj.id):
                labels_linked += 1

        # 4. Release (album)
        album = raw.get("album")
        if album and album.get("title"):
            release = await self._get_or_create_release(album, label_obj)
            if await self._link_track_release(track_id, release.id):
                releases_linked += 1

        # 5. Clean up track title (remove "Artist1, Artist2 - " prefix)
        title_cleaned = False
        if artists_linked > 0:
            title_cleaned = await self._clean_track_title(track_id, raw["artists"])

        return {
            "track_id": track_id,
            "artists": artists_linked,
            "genres": genres_linked,
            "labels": labels_linked,
            "releases": releases_linked,
            "title_cleaned": title_cleaned,
        }

    async def normalize_playlist(self, playlist_id: int) -> dict[str, Any]:
        """Normalize metadata for all tracks in a playlist.

        Returns summary with per-track results and totals.
        """
        from app.models.playlist import PlaylistItem

        stmt = (
            select(PlaylistItem.track_id)
            .where(PlaylistItem.playlist_id == playlist_id)
            .order_by(PlaylistItem.sort_index)
        )
        result = await self._session.execute(stmt)
        track_ids = [row[0] for row in result.all()]

        total_artists = 0
        total_genres = 0
        total_labels = 0
        total_releases = 0
        processed = 0

        for tid in track_ids:
            res = await self.normalize_track_metadata(tid)
            total_artists += res["artists"]
            total_genres += res["genres"]
            total_labels += res["labels"]
            total_releases += res["releases"]
            processed += 1

        return {
            "playlist_id": playlist_id,
            "tracks_processed": processed,
            "artists_linked": total_artists,
            "genres_linked": total_genres,
            "labels_linked": total_labels,
            "releases_linked": total_releases,
        }

    # ── Data extraction ──────────────────────────────────

    async def _extract_raw_data(
        self,
        track_id: int,
        ym_track: Any | None,
    ) -> dict[str, Any] | None:
        """Extract normalized raw data dict from YMTrack or YandexMetadata.

        Returns dict with keys: artists, genre, label, album.
        """
        if ym_track is not None:
            return self._extract_from_ym_track(ym_track)

        # Fallback: load from YandexMetadata
        stmt = select(YandexMetadata).where(YandexMetadata.track_id == track_id)
        result = await self._session.execute(stmt)
        meta = result.scalar_one_or_none()
        if meta is None:
            return None

        raw = self._extract_from_ym_metadata(meta)

        # Artist info is not stored in YandexMetadata — parse from track title
        if not raw["artists"]:
            raw["artists"] = await self._extract_artists_from_title(track_id)

        return raw

    def _extract_from_ym_track(self, ym_track: Any) -> dict[str, Any]:
        """Extract data from a YMTrack API response object."""
        artists_raw: list[dict[str, Any]] = getattr(ym_track, "artists", None) or []
        artists = [
            {"name": str(a.get("name", "")), "role": "primary"}
            for a in artists_raw
            if a.get("name")
        ]

        albums_raw: list[dict[str, Any]] = getattr(ym_track, "albums", None) or []
        album = albums_raw[0] if albums_raw else {}

        genre = album.get("genre") if album else None

        # Label: try albums[0].labels[0].name first, then album-level label
        label = None
        if album:
            album_labels = album.get("labels", [])
            if album_labels and isinstance(album_labels, list):
                first_label = album_labels[0]
                if isinstance(first_label, dict):
                    label = first_label.get("name")
                elif isinstance(first_label, str):
                    label = first_label

        album_data = None
        if album and album.get("title"):
            album_data = {
                "title": album.get("title", ""),
                "year": album.get("year"),
                "type": album.get("type"),
            }

        return {
            "artists": artists,
            "genre": genre,
            "label": label,
            "album": album_data,
        }

    def _extract_from_ym_metadata(self, meta: YandexMetadata) -> dict[str, Any]:
        """Extract data from stored YandexMetadata row.

        Note: artist info is not stored in YandexMetadata — artists are
        extracted from the track title in ``_extract_raw_data``.
        """
        album_data = None
        if meta.album_title:
            album_data = {
                "title": meta.album_title,
                "year": meta.album_year,
                "type": meta.album_type,
            }

        return {
            "artists": [],
            "genre": meta.album_genre,
            "label": meta.label,
            "album": album_data,
        }

    async def _extract_artists_from_title(self, track_id: int) -> list[dict[str, str]]:
        """Parse artist names from track title in 'Artist1, Artist2 - Title' format."""
        stmt = select(Track.title).where(Track.id == track_id)
        result = await self._session.execute(stmt)
        title = result.scalar_one_or_none()
        if not title or " - " not in title:
            return []

        artist_part = title.split(" - ", 1)[0]
        names = [n.strip() for n in artist_part.split(",")]
        return [{"name": n, "role": "primary"} for n in names if n]

    # ── Get-or-create helpers ────────────────────────────

    async def _get_or_create_artist(self, name: str) -> Artist:
        """Find existing artist by name or create a new one."""
        stmt = select(Artist).where(Artist.name == name)
        result = await self._session.execute(stmt)
        artist = result.scalar_one_or_none()
        if artist is not None:
            return artist

        artist = Artist(name=name)
        self._session.add(artist)
        await self._session.flush()
        return artist

    async def _get_or_create_genre(self, name: str) -> Genre:
        """Find existing genre by name or create a new one."""
        stmt = select(Genre).where(Genre.name == name).limit(1)
        result = await self._session.execute(stmt)
        genre = result.scalar_one_or_none()
        if genre is not None:
            return genre

        genre = Genre(name=name)
        self._session.add(genre)
        await self._session.flush()
        return genre

    async def _get_or_create_label(self, name: str) -> Label:
        """Find existing label by name or create a new one."""
        stmt = select(Label).where(Label.name == name)
        result = await self._session.execute(stmt)
        label = result.scalar_one_or_none()
        if label is not None:
            return label

        label = Label(name=name)
        self._session.add(label)
        await self._session.flush()
        return label

    async def _get_or_create_release(
        self,
        album_data: dict[str, Any],
        label: Label | None,
    ) -> Release:
        """Find existing release by title+year or create a new one."""
        title = album_data["title"]
        year = album_data.get("year")
        release_type = album_data.get("type")

        # Build release_date from year
        release_date_val = None
        if year is not None:
            with contextlib.suppress(ValueError, TypeError):
                release_date_val = date(year, 1, 1)

        # Match by title + year (if year available) to avoid duplicates
        stmt = select(Release).where(Release.title == title)
        if release_date_val is not None:
            stmt = stmt.where(Release.release_date == release_date_val)

        result = await self._session.execute(stmt)
        release = result.scalars().first()
        if release is not None:
            # Update label if it was missing
            if release.label_id is None and label is not None:
                release.label_id = label.id
                await self._session.flush()
            return release

        release = Release(
            title=title,
            label_id=label.id if label else None,
            release_date=release_date_val,
            release_type=release_type,
        )
        self._session.add(release)
        await self._session.flush()
        return release

    # ── Junction linking helpers ──────────────────────────

    async def _link_track_artist(self, track_id: int, artist_id: int, role: str) -> bool:
        """Link track to artist if not already linked. Returns True if new link created."""
        stmt = select(TrackArtist).where(
            TrackArtist.track_id == track_id,
            TrackArtist.artist_id == artist_id,
            TrackArtist.role == role,
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return False

        self._session.add(TrackArtist(track_id=track_id, artist_id=artist_id, role=role))
        await self._session.flush()
        return True

    async def _link_track_genre(self, track_id: int, genre_id: int) -> bool:
        """Link track to genre if not already linked."""
        stmt = select(TrackGenre).where(
            TrackGenre.track_id == track_id,
            TrackGenre.genre_id == genre_id,
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return False

        self._session.add(TrackGenre(track_id=track_id, genre_id=genre_id))
        await self._session.flush()
        return True

    async def _link_track_label(self, track_id: int, label_id: int) -> bool:
        """Link track to label if not already linked."""
        stmt = select(TrackLabel).where(
            TrackLabel.track_id == track_id,
            TrackLabel.label_id == label_id,
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return False

        self._session.add(TrackLabel(track_id=track_id, label_id=label_id))
        await self._session.flush()
        return True

    async def _link_track_release(self, track_id: int, release_id: int) -> bool:
        """Link track to release if not already linked."""
        stmt = select(TrackRelease).where(
            TrackRelease.track_id == track_id,
            TrackRelease.release_id == release_id,
        )
        result = await self._session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return False

        self._session.add(TrackRelease(track_id=track_id, release_id=release_id))
        await self._session.flush()
        return True

    # ── Title cleanup ────────────────────────────────────

    async def _clean_track_title(
        self,
        track_id: int,
        artists: list[dict[str, Any]],
    ) -> bool:
        """Remove artist prefix from track title if it matches 'Artists - Title' pattern.

        Returns True if title was cleaned.
        """
        stmt = select(Track).where(Track.id == track_id)
        result = await self._session.execute(stmt)
        track = result.scalar_one_or_none()
        if track is None or " - " not in track.title:
            return False

        # Build expected artist prefix
        artist_names = [a.get("name", "") for a in artists if a.get("name")]
        if not artist_names:
            return False

        expected_prefix = ", ".join(artist_names)
        if track.title.startswith(f"{expected_prefix} - "):
            clean_title = track.title[len(expected_prefix) + 3 :]  # " - " = 3 chars
            if clean_title:
                track.title = clean_title
                await self._session.flush()
                return True

        return False
