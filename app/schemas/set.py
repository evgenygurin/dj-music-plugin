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
    source_playlist_id__eq: int | None = None


class SetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=500)
    description: str | None = None
    target_duration_ms: int | None = Field(default=None, ge=60_000, le=12 * 3600_000)
    target_bpm_min: int | None = Field(default=None, ge=60, le=250)
    target_bpm_max: int | None = Field(default=None, ge=60, le=250)
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
    set_id__eq: int | None = None
    set_id__in: list[int] | None = None
    label__icontains: str | None = None


class SetVersionCreate(BaseModel):
    """Build a new set version via the GA/greedy build handler.

    ``label`` is the canonical version name; ``version_label`` accepted as
    an alias for older callers (handler reads either). ``generator_run_meta``
    captures algo + params for traceability (e.g. ``{"algorithm": "ga",
    "template": "peak_hour_60"}``).
    """

    model_config = ConfigDict(extra="forbid")
    set_id: int = Field(..., description="Parent set id.")
    label: str | None = Field(default=None, description="Version label (alias for version_label).")
    version_label: str | None = Field(default=None, description="Version label — alias of label.")
    track_order: list[int] = Field(
        ..., min_length=1, description="Ordered track ids to persist as set items."
    )
    quality_score: float | None = Field(default=None, ge=0.0, le=1.0)
    generator_run_meta: JsonDictOrNone = Field(
        default=None,
        description='Generator metadata, e.g. {"algorithm": "ga", "template": "peak_hour_60"}.',
    )
