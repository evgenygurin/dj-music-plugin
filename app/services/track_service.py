"""Track service — business logic for track CRUD, search, and features.

Framework-agnostic: no MCP/FastMCP imports.
"""

from __future__ import annotations

from typing import Any

from app.core.errors import NotFoundError, ValidationError
from app.core.pagination import CursorPage
from app.core.schemas import TrackBrief, TrackStandard
from app.models.audio import TrackAudioFeaturesComputed
from app.models.track import Track
from app.repositories.feature import FeatureRepository
from app.repositories.track import TrackRepository


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

    # ── Write ────────────────────────────────────────

    async def create(self, title: str, duration_ms: int | None = None) -> Track:
        if not title:
            raise ValidationError("title is required")
        track = Track(title=title, duration_ms=duration_ms, status=0)
        return await self._tracks.create(track)

    async def update(self, track_id: int, **fields: Any) -> Track:
        track = await self.get_by_id(track_id)
        for key, value in fields.items():
            if hasattr(track, key):
                setattr(track, key, value)
        return await self._tracks.update(track)

    async def archive(self, track_id: int) -> Track:
        track = await self.get_by_id(track_id)
        track.status = 1
        return await self._tracks.update(track)

    async def unarchive(self, track_id: int) -> Track:
        track = await self.get_by_id(track_id)
        track.status = 0
        return await self._tracks.update(track)

    # ── Converters ───────────────────────────────────

    @staticmethod
    def to_brief(track: Track) -> TrackBrief:
        return TrackBrief(
            id=track.id,
            title=track.title,
            artist_names=[],
            bpm=None,
            key_camelot=None,
            duration_ms=track.duration_ms,
        )

    @staticmethod
    def to_standard(
        track: Track,
        features: TrackAudioFeaturesComputed | None = None,
    ) -> TrackStandard:
        return TrackStandard(
            id=track.id,
            title=track.title,
            artist_names=[],
            bpm=features.bpm if features else None,
            key_camelot=None,
            duration_ms=track.duration_ms,
            energy_lufs=features.integrated_lufs if features else None,
            mood=features.mood if features else None,
            status=track.status,
            has_features=features is not None,
        )
