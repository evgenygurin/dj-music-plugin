"""Audio feature DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TrackFeaturesView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    track_id: int
    analysis_level: int = 0
    bpm: float | None = None
    key_code: int | None = None
    integrated_lufs: float | None = None
    energy_mean: float | None = None
    spectral_centroid_hz: float | None = None
    hp_ratio: float | None = None
    kick_prominence: float | None = None
    mood: str | None = None
    mood_confidence: float | None = None


class TrackFeaturesFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    track_id__eq: int | None = None
    track_id__in: list[int] | None = None
    analysis_level__eq: int | None = None
    analysis_level__gte: int | None = None
    analysis_level__lt: int | None = None
    bpm__eq: float | None = None
    bpm__gte: float | None = None
    bpm__lte: float | None = None
    bpm__range: list[float] | None = None
    # key_code: full lookup family. Audit iter 6 caught ``key_code__in``
    # rejected even though every harmonic compatibility query
    # ("tracks in 8A or 8B") needs it.
    key_code__eq: int | None = None
    key_code__in: list[int] | None = None
    key_code__range: list[int] | None = None
    # integrated_lufs: range/gte/lte for loudness-bucket queries.
    integrated_lufs__gte: float | None = None
    integrated_lufs__lte: float | None = None
    integrated_lufs__range: list[float] | None = None
    mood__eq: str | None = None
    mood__in: list[str] | None = None
    mood__isnull: bool | None = None
    # Confidence + scalar feature lookups (audit iter 25). The most
    # common analytics query is "filter by mood_confidence >= 0.1
    # to exclude low-quality classifications".
    mood_confidence__gte: float | None = None
    mood_confidence__lte: float | None = None
    energy_mean__gte: float | None = None
    energy_mean__lte: float | None = None
    spectral_centroid_hz__gte: float | None = None
    spectral_centroid_hz__lte: float | None = None
    hp_ratio__gte: float | None = None
    hp_ratio__lte: float | None = None
    kick_prominence__gte: float | None = None
    kick_prominence__lte: float | None = None


class TrackFeaturesCreate(BaseModel):
    """Creation triggers the audio pipeline via custom handler."""

    model_config = ConfigDict(extra="forbid")
    track_id: int | None = None
    track_ids: list[int] | None = None
    level: int = Field(default=3, ge=1, le=5)


class TrackFeaturesUpdate(BaseModel):
    """Reanalyze with a higher level."""

    model_config = ConfigDict(extra="forbid")
    level: int = Field(..., ge=1, le=5)
