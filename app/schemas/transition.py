"""Transition DTOs."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


def _check_distinct_endpoints(from_id: int, to_id: int) -> None:
    """Audit iter 54 (T-52): a transition from a track to itself is
    logically meaningless — every component would compare the track
    against its own features and report perfect similarity. Without
    this guard ``entity_create(transition, {"from_track_id":146,
    "to_track_id":146})`` happily produced a 0.93 self-score row.
    """
    if from_id == to_id:
        raise ValueError(f"from_track_id and to_track_id must differ; got {from_id} for both")


class TransitionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_track_id: int
    to_track_id: int
    overall_quality: float | None = None
    bpm_score: float | None = None
    harmonics_score: float | None = None
    energy_score: float | None = None
    bass_score: float | None = None
    drums_score: float | None = None
    vocals_score: float | None = None
    # Compound / derived scores persisted by ``transition_persist`` handler.
    # Audit iter 38: missing from the View → ``entity_get`` / list could not
    # surface the harmonic-distance-weighted score nor the low-band conflict
    # score, both of which the scorer writes back and consumers (panel,
    # set-review tools) want to read directly.
    key_distance_weighted: float | None = None
    low_conflict_score: float | None = None
    hard_reject: bool | None = None
    # ``reject_reason`` mirrors the column on the model and the field
    # already returned by ``local://transition/{a}/{b}/score`` -
    # without it on the View, ``entity_get(transition, id)`` couldn't
    # tell consumers WHY a pair was rejected (audit iter 8).
    reject_reason: str | None = None
    fx_type: str | None = None
    # Mix-execution metadata: bars to mix over, section anchors, raw
    # overlap window. Audit iter 38: persisted by the transition handler
    # but invisible on the View → caller had to ``entity_update`` to write
    # but had no way to read what they previously wrote. Plus
    # ``transition_recipe_json`` is the JSON recipe blob produced by
    # ``recipe_engine.generate`` and equally needed in read paths.
    transition_bars: int | None = None
    from_section_id: int | None = None
    to_section_id: int | None = None
    overlap_ms: int | None = None
    transition_recipe_json: str | None = None


class TransitionFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Primary key lookups — audit iter 38: missing from the filter so
    # callers couldn't ``entity_list(transition, filters={"id__in":[...]})``
    # for the canonical "load these N specific scored pairs" query.
    id__eq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__gte: int | None = None
    id__lt: int | None = None
    id__lte: int | None = None
    from_track_id__eq: int | None = None
    to_track_id__eq: int | None = None
    from_track_id__in: list[int] | None = None
    to_track_id__in: list[int] | None = None
    overall_quality__gte: float | None = None
    overall_quality__lte: float | None = None
    overall_quality__range: list[float] | None = None
    # hard_reject: canonical "show me transitions that violate hard
    # constraints" query - audit iter 7 caught the missing lookup.
    hard_reject__eq: bool | None = None
    # reject_reason: text search to find pairs rejected for the same
    # cause ("BPM diff", "Camelot distance") - audit iter 19.
    reject_reason__icontains: str | None = None
    reject_reason__isnull: bool | None = None
    # Component scores: filter by individual scoring component (audit
    # iter 22). "Find pairs with high BPM compatibility but weak
    # harmonic" - the canonical scoring-debug query.
    bpm_score__gte: float | None = None
    bpm_score__lte: float | None = None
    harmonics_score__gte: float | None = None
    harmonics_score__lte: float | None = None
    energy_score__gte: float | None = None
    energy_score__lte: float | None = None
    bass_score__gte: float | None = None
    bass_score__lte: float | None = None
    drums_score__gte: float | None = None
    drums_score__lte: float | None = None
    vocals_score__gte: float | None = None
    vocals_score__lte: float | None = None
    # fx_type: which transition style was tagged on a persisted pair.
    fx_type__eq: str | None = None
    fx_type__in: list[str] | None = None
    # Compound / derived scores — same drift class as the component
    # filters above. Audit iter 38.
    key_distance_weighted__gte: float | None = None
    key_distance_weighted__lte: float | None = None
    low_conflict_score__gte: float | None = None
    low_conflict_score__lte: float | None = None
    # Mix-execution metadata filters: "show me 32-bar mixes",
    # "show pairs with overlap > 16 sec".
    transition_bars__eq: int | None = None
    transition_bars__in: list[int] | None = None
    transition_bars__gte: int | None = None
    transition_bars__lte: int | None = None
    overlap_ms__gte: int | None = None
    overlap_ms__lte: int | None = None


class TransitionCreate(BaseModel):
    """Create triggers compute-score-then-persist via custom handler."""

    model_config = ConfigDict(extra="forbid")
    from_track_id: int
    to_track_id: int
    persist: bool = True
    scoring_profile: str | None = None

    @model_validator(mode="after")
    def _validate_distinct_endpoints(self) -> Self:
        _check_distinct_endpoints(self.from_track_id, self.to_track_id)
        return self


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
