"""ScoringProfile DTOs."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Audit iter 51 (T-49): the 6 component weights are convex-combination
# weights — they must sum to 1.0 for the resulting score to stay in
# [0, 1]. Without this guard ``entity_create(scoring_profile, ...)``
# accepted a profile with all-0.5 weights (sum 3.0) which would
# produce nonsensical out-of-range scores when applied. ``epsilon``
# tolerates float drift; the scorer rebalances via DEFAULT_WEIGHTS
# but a persisted bogus profile would mask the bug.
_WEIGHT_FIELDS: tuple[str, ...] = (
    "bpm_weight",
    "harmonics_weight",
    "energy_weight",
    "bass_weight",
    "drums_weight",
    "vocals_weight",
)
_WEIGHT_SUM_EPS = 0.001


def _check_weights_sum_to_one(model: object) -> None:
    """Raise ValueError if the 6 weight fields don't sum to ~1.0.

    Skips the check on partial updates where any weight is ``None`` —
    the cross-row invariant can't be enforced without a DB read.
    """
    raw = [getattr(model, f, None) for f in _WEIGHT_FIELDS]
    if any(w is None for w in raw):
        return
    weights: list[float] = [float(w) for w in raw if w is not None]
    total = sum(weights)
    if abs(total - 1.0) > _WEIGHT_SUM_EPS:
        pairs = ", ".join(f"{f}={w}" for f, w in zip(_WEIGHT_FIELDS, weights, strict=True))
        raise ValueError(
            f"scoring_profile weights must sum to 1.0 (±{_WEIGHT_SUM_EPS}); "
            f"got {total:.4f} ({pairs})"
        )


class ScoringProfileView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    bpm_weight: float
    harmonics_weight: float
    energy_weight: float
    bass_weight: float
    drums_weight: float
    vocals_weight: float
    description: str | None = None


class ScoringProfileFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__eq: int | None = None
    id__in: list[int] | None = None
    name__eq: str | None = None
    name__icontains: str | None = None
    # Component weights: "find harmonic-focused profiles" (audit iter
    # 24). Same shape as the 6-component filters on Transition /
    # TransitionHistory.
    bpm_weight__gte: float | None = None
    bpm_weight__lte: float | None = None
    harmonics_weight__gte: float | None = None
    harmonics_weight__lte: float | None = None
    energy_weight__gte: float | None = None
    energy_weight__lte: float | None = None
    bass_weight__gte: float | None = None
    bass_weight__lte: float | None = None
    drums_weight__gte: float | None = None
    drums_weight__lte: float | None = None
    vocals_weight__gte: float | None = None
    vocals_weight__lte: float | None = None


class ScoringProfileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=100)
    bpm_weight: float = Field(..., ge=0.0, le=1.0)
    harmonics_weight: float = Field(..., ge=0.0, le=1.0)
    energy_weight: float = Field(..., ge=0.0, le=1.0)
    bass_weight: float = Field(..., ge=0.0, le=1.0)
    drums_weight: float = Field(..., ge=0.0, le=1.0)
    vocals_weight: float = Field(..., ge=0.0, le=1.0)
    description: str | None = None

    @model_validator(mode="after")
    def _validate_weight_sum(self) -> Self:
        _check_weights_sum_to_one(self)
        return self


class ScoringProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bpm_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    harmonics_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    energy_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    bass_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    drums_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    vocals_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    description: str | None = None

    @model_validator(mode="after")
    def _validate_weight_sum(self) -> Self:
        # Only enforce the sum invariant when ALL 6 weights are
        # supplied — partial patches cannot be checked here without
        # a DB read of the existing row's values.
        _check_weights_sum_to_one(self)
        return self
