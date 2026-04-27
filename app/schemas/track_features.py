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
    """Creation triggers the audio pipeline via the analyze handler.

    The handler operates in batch — pass ``track_ids`` (singular
    ``track_id`` is NOT accepted; wrap in a one-element list).
    ``force=True`` re-runs analysis even when the cached level already
    meets ``level``.
    """

    model_config = ConfigDict(extra="forbid")
    track_ids: list[int] = Field(
        ..., min_length=1, description="One or more track ids to analyze."
    )
    level: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Target analysis level (L1..L5; L3 = scoring tier).",
    )
    force: bool = Field(
        default=False,
        description="Re-analyze even when current_level >= target.",
    )


class TrackFeaturesUpdate(BaseModel):
    """Reanalyze a single track at a higher level via reanalyze handler.

    The track id comes from the ``entity_update(id=...)`` path argument
    (dispatcher injects it), so callers only supply the new ``level``
    here. ``force`` re-runs the pipeline even when current_level >= level.
    """

    model_config = ConfigDict(extra="forbid")
    level: int = Field(..., ge=1, le=5, description="Target analysis level.")
    force: bool = Field(
        default=False,
        description="Re-run pipeline even when current_level already meets level.",
    )
