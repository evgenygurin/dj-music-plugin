"""TransitionHistory DTOs."""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TransitionHistoryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    overall_score: float | None = None
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
    user_reaction: Literal["positive", "neutral", "negative"] | None = None
    session_id: str | None = None


class TransitionHistoryFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id__eq: int | None = None
    from_track_id__in: list[int] | None = None
    to_track_id__eq: int | None = None
    to_track_id__in: list[int] | None = None
    user_reaction__eq: Literal["positive", "neutral", "negative"] | None = None
    overall_score__gte: float | None = None
    overall_score__lte: float | None = None
    overall_score__range: list[float] | None = None
    session_id__eq: str | None = None
    # style: filter by mix-style label (e.g. ``bass_swap_short``,
    # ``long_blend``) - audit iter 21.
    style__eq: str | None = None
    style__in: list[str] | None = None
    style__icontains: str | None = None
    # duration_sec: filter by transition length - audit iter 22.
    duration_sec__gte: float | None = None
    duration_sec__lte: float | None = None
    duration_sec__range: list[float] | None = None
    # Component scores: same as TransitionFilter for symmetry. Audit
    # iter 23 caught the missing lookups when reviewing the analytics
    # surface ("which transitions had high BPM compatibility but the
    # DJ rated them poorly?" was unanswerable).
    bpm_score__gte: float | None = None
    bpm_score__lte: float | None = None
    harmonic_score__gte: float | None = None
    harmonic_score__lte: float | None = None
    energy_score__gte: float | None = None
    energy_score__lte: float | None = None
    spectral_score__gte: float | None = None
    spectral_score__lte: float | None = None
    groove_score__gte: float | None = None
    groove_score__lte: float | None = None
    timbral_score__gte: float | None = None
    timbral_score__lte: float | None = None
    # tempo_match_ratio: how closely the BPMs aligned in practice.
    tempo_match_ratio__gte: float | None = None
    tempo_match_ratio__lte: float | None = None


class TransitionHistoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    overall_score: float | None = Field(default=None, ge=0.0, le=1.0)
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
    user_reaction: Literal["positive", "neutral", "negative"] | None = None
    session_id: str | None = None

    @model_validator(mode="after")
    def _validate_distinct_endpoints(self) -> Self:
        # Audit iter 54 (T-52): same as TransitionCreate. A transition
        # history row from a track to itself is meaningless — nothing
        # was actually mixed.
        if self.from_track_id == self.to_track_id:
            raise ValueError(
                f"from_track_id and to_track_id must differ; got {self.from_track_id} for both"
            )
        return self


class TransitionHistoryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_reaction: Literal["positive", "neutral", "negative"] | None = None
    style: str | None = None
    duration_sec: float | None = None
    tempo_match_ratio: float | None = None
