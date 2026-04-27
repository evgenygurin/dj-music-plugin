"""DJ set DTOs — covers DjSet + DjSetVersion via nested create helpers."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.shared.types import JsonDictOrNone


class SetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None = None
    target_duration_ms: int | None = None
    target_bpm_min: int | None = None
    target_bpm_max: int | None = None
    template_name: str | None = None
    source_playlist_id: int | None = None
    version_count: int | None = None


class SetFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id__eq: int | None = None
    id__in: list[int] | None = None
    name__eq: str | None = None
    name__icontains: str | None = None
    template_name__eq: str | None = None
    # template_name__in: "show me sets built with classic_60 or
    # peak_hour_60" - audit iter 12 caught the missing lookup.
    template_name__in: list[str] | None = None
    source_playlist_id__eq: int | None = None
    source_playlist_id__in: list[int] | None = None
    # target_bpm_min / target_bpm_max — range queries to find sets in
    # a particular tempo bucket (audit iter 17).
    target_bpm_min__gte: int | None = None
    target_bpm_min__lte: int | None = None
    target_bpm_max__gte: int | None = None
    target_bpm_max__lte: int | None = None
    # target_duration_ms — for "find 60-90 min sets" queries.
    target_duration_ms__gte: int | None = None
    target_duration_ms__lte: int | None = None


class SetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    target_duration_ms: int | None = Field(default=None, ge=60_000, le=12 * 3600_000)
    target_bpm_min: int | None = Field(default=None, ge=60, le=250)
    target_bpm_max: int | None = Field(default=None, ge=60, le=250)
    # ``template_name`` is validated against the template registry by
    # ``app.tools.entity.create`` (audit iter 16 / T-16). The check
    # lives at the dispatcher rather than here because schemas cannot
    # import ``app.domain`` per the v2-server import contract.
    template_name: str | None = None
    source_playlist_id: int | None = None


class SetUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = None
    description: str | None = None
    target_duration_ms: int | None = None
    template_name: str | None = None


class SetVersionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    set_id: int
    label: str
    quality_score: float | None = None
    # generator_run_meta is stored as ``Text`` in the ORM (JSON-encoded). The
    # coercing type transparently parses the string back into a dict so this
    # view is usable from ``entity_list`` without a separate mapping pass.
    generator_run_meta: JsonDictOrNone = None


class SetVersionFilter(BaseModel):
    """Filter schema for the ``set_version`` entity.

    Kept separate from ``SetFilter`` because the two entities share neither
    searchable fields nor filterable columns — ``set_version`` searches by
    ``label`` (mapped to ``label__icontains`` by the generic list tool) and
    filters by ``set_id``.
    """

    model_config = ConfigDict(extra="forbid")
    id__in: list[int] | None = None
    id__eq: int | None = None
    # id range lookups - audit iter 27.
    id__gt: int | None = None
    id__gte: int | None = None
    id__lt: int | None = None
    id__lte: int | None = None
    set_id__eq: int | None = None
    set_id__in: list[int] | None = None
    label__icontains: str | None = None
    # label__eq: exact label match - "find the v1 build of set 5"
    # (audit iter 13).
    label__eq: str | None = None
    # quality_score: full numeric lookups - "find versions with
    # quality >= 0.7" was the canonical "is this set good enough"
    # query and used to be rejected (audit iter 8).
    quality_score__gte: float | None = None
    quality_score__lte: float | None = None
    quality_score__range: list[float] | None = None


class SetVersionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: int
    label: str
    track_order: list[int]
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    generator_run_meta: JsonDictOrNone = None
