"""Transition DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class TransitionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    overall_quality: float | None = None
    bpm_score: float | None = None
    harmonic_score: float | None = None
    energy_score: float | None = None
    spectral_score: float | None = None
    groove_score: float | None = None
    timbral_score: float | None = None
    hard_reject: bool | None = None
    fx_type: str | None = None


class TransitionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_track_id__eq: int | None = None
    to_track_id__eq: int | None = None
    from_track_id__in: list[int] | None = None
    to_track_id__in: list[int] | None = None
    overall_quality__gte: float | None = None


class TransitionCreate(BaseModel):
    """Create triggers compute-score-then-persist via custom handler."""

    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    persist: bool = True
    scoring_profile: str | None = None


class TransitionUpdate(BaseModel):
    """Overwrite recipe / flags on an existing row (no rescoring).

    Rescoring happens through ``entity_create(entity="transition")`` (a
    fresh ``transition_persist`` handler run); update is for human-edited
    recipe overrides and feedback fields only.
    """

    model_config = ConfigDict(extra="forbid")
    fx_type: str | None = Field(default=None, min_length=1, max_length=50)
    transition_bars: int | None = Field(default=None, ge=0, le=256)
    transition_recipe_json: str | None = None
    reject_reason: str | None = Field(default=None, max_length=255)
