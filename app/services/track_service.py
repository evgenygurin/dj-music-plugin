"""Track service — business logic for track CRUD, search, and features.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.core.schemas import TrackBrief, TrackStandard
from app.core.utils.pagination import CursorPage
from app.models.audio import TrackAudioFeaturesComputed
from app.models.track import Track
from app.repositories.feature import FeatureRepository
from app.repositories.track import TrackRepository

_LEADING_ARTICLES = re.compile(r"^(the|a|an)\s+", re.IGNORECASE)
_NON_ALNUM_PREFIX = re.compile(r"^[^a-z0-9\u00C0-\u024F]+")
_YM_PREFIX = re.compile(r"^ym:(\d+)$", re.IGNORECASE)


def _extract_ym_id(query: str) -> str | None:
    """Return the bare YM ID if ``query`` is ``ym:<digits>``, else ``None``."""
    if not query:
        return None
    match = _YM_PREFIX.match(query.strip())
    return match.group(1) if match else None


def generate_sort_title(title: str) -> str:
    """Generate a sort-friendly title: lowercase, strip articles and non-alnum prefix."""
    result = title.lower().strip()
    result = _LEADING_ARTICLES.sub("", result)
    result = _NON_ALNUM_PREFIX.sub("", result)
    return result or title.lower().strip()


class TrackService:
    """Business logic for tracks: CRUD, search, feature access."""

    def __init__(
        self,
        track_repo: TrackRepository,
        feature_repo: FeatureRepository,
    ) -> None:
        self._tracks = track_repo
        self._features = feature_repo

    # ── Read ─────────────────────────────────────────

    async def get_by_id(self, track_id: int) -> Track:
        track = await self._tracks.get_by_id(track_id)
        if track is None:
            raise NotFoundError("Track", track_id)
        return track

    async def get_with_features(
        self, track_id: int
    ) -> tuple[Track, TrackAudioFeaturesComputed | None]:
        """Return track + its audio features (or None)."""
        track = await self.get_by_id(track_id)
        features = await self._features.get_features(track_id)
        return track, features

    async def search(self, query: str, limit: int = 10) -> list[Track]:
        """Search tracks by text or external ID.

        ``ym:12345`` / ``YM:12345`` looks up the YM external ID directly
        and returns the linked track (or an empty list). All other queries
        fall through to text search across title and artist names.
        """
        ym_id = _extract_ym_id(query)
        if ym_id is not None:
            link = await self._tracks.get_by_external_id("yandex_music", ym_id)
            if link is None:
                return []
            track = await self._tracks.get_by_id(link.track_id)
            return [track] if track is not None else []
        return await self._tracks.search_by_text(query, limit=limit)

    async def list_all(self, *, limit: int = 20, cursor: str | None = None) -> CursorPage[Track]:
        return await self._tracks.list_all(limit=limit, cursor=cursor)

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
        return await self._tracks.filter_by_features(
            bpm_min=bpm_min,
            bpm_max=bpm_max,
            key_code=key_code,
            energy_min=energy_min,
            energy_max=energy_max,
            limit=limit,
            cursor=cursor,
        )

    async def get_artist_names_batch(self, track_ids: list[int]) -> dict[int, list[str]]:
        """Get artist names for multiple tracks. Returns {track_id: [name, ...]}."""
        return await self._tracks.get_artist_names_batch(track_ids)

    async def get_track_sections(self, track_id: int) -> list[dict[str, Any]]:
        """Return sections for a track as dicts."""
        sections = await self._features.get_sections(track_id)
        return [
            {"type": s.section_type, "start_ms": s.start_ms, "end_ms": s.end_ms} for s in sections
        ]

    # ── Write ────────────────────────────────────────

    async def create(self, title: str, duration_ms: int | None = None) -> Track:
        if not title:
            raise ValidationError("title is required")
        existing = await self._tracks.get_by_title(title)
        if existing:
            from app.core.errors import ConflictError

            raise ConflictError(f"Track with title '{title}' already exists (id={existing.id})")
        track = Track(
            title=title,
            sort_title=generate_sort_title(title),
            duration_ms=duration_ms,
            status=0,
        )
        return await self._tracks.create(track)

    async def update(self, track_id: int, **fields: Any) -> Track:
        track = await self.get_by_id(track_id)
        for key, value in fields.items():
            if hasattr(track, key):
                setattr(track, key, value)
        # Re-generate sort_title when title changes
        if "title" in fields:
            track.sort_title = generate_sort_title(track.title)
        return await self._tracks.update(track)

    async def archive(self, track_id: int) -> Track:
        track = await self.get_by_id(track_id)
        track.status = 1
        return await self._tracks.update(track)

    async def unarchive(self, track_id: int) -> Track:
        track = await self.get_by_id(track_id)
        track.status = 0
        return await self._tracks.update(track)

    async def get_platform_counts(self) -> dict[str, int]:
        """Return count of linked tracks per platform."""
        return await self._tracks.get_platform_counts()

    # ── Converters ───────────────────────────────────

    @staticmethod
    def _features_to_camelot(
        features: TrackAudioFeaturesComputed | None,
    ) -> str | None:
        """Convert key_code from features to Camelot notation."""
        if features and features.key_code is not None:
            from app.core.camelot import key_code_to_camelot

            return key_code_to_camelot(features.key_code)
        return None

    @staticmethod
    def to_brief(
        track: Track,
        features: TrackAudioFeaturesComputed | None = None,
        artist_names: list[str] | None = None,
    ) -> TrackBrief:
        return TrackBrief(
            id=track.id,
            title=track.title,
            artist_names=artist_names or [],
            bpm=features.bpm if features else None,
            key_camelot=TrackService._features_to_camelot(features),
            duration_ms=track.duration_ms,
        )

    @staticmethod
    def to_standard(
        track: Track,
        features: TrackAudioFeaturesComputed | None = None,
        artist_names: list[str] | None = None,
    ) -> TrackStandard:
        return TrackStandard(
            id=track.id,
            title=track.title,
            artist_names=artist_names or [],
            bpm=features.bpm if features else None,
            key_camelot=TrackService._features_to_camelot(features),
            duration_ms=track.duration_ms,
            energy_lufs=features.integrated_lufs if features else None,
            mood=features.mood if features else None,
            status=track.status,
            has_features=features is not None,
        )
