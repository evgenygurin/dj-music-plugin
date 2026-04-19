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
    mood__eq: str | None = None
    mood__in: list[str] | None = None


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
