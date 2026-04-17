"""Structured MCP outputs for DJ set tools: commit, arc preview, templates, scoring."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ListSetsResult(BaseModel):
    """Paginated ``list_sets`` payload (items, next_cursor, total)."""

    items: list[dict[str, Any]]
    next_cursor: str | None = None
    total: int = 0


class SetVersionResult(BaseModel):
    """Result of committing a set version."""

    set_id: int
    version_id: int
    version_label: str | None = None
    track_count: int
    quality_score: float | None = None
    template: str | None = None


class TransitionScoreResult(BaseModel):
    """Transition score between two tracks."""

    mode: str
    scores: list[dict[str, object]] | None = None
    pair_score: dict[str, object] | None = None
    candidates: list[dict[str, object]] | None = None


class SetArcPreview(BaseModel):
    """Preview of a set arc — same fields as ``PreviewResult`` in ``app.optimization.preview``."""

    score: float = Field(description="Overall arc quality 0-1")
    energy_arc: list[float]
    bpm_arc: list[float]
    weak_spots: list[int] = Field(
        description="0-based positions (outgoing track) where transition score is below threshold",
    )
    recommendation: str
    missing_track_ids: list[int]


class SetTemplateSlotRow(BaseModel):
    """One slot row in a registered set template."""

    position: float
    target_mood: str | None
    energy_lufs: float
    bpm_min: float
    bpm_max: float
    duration_ms: int
    flexibility: float


class SetTemplateEntry(BaseModel):
    """Registered DJ set template with slot definitions."""

    name: str
    duration_min: int
    description: str
    slots: list[SetTemplateSlotRow]


class GetSetTemplatesResult(BaseModel):
    """Response from ``get_set_templates``."""

    templates: list[SetTemplateEntry]


class TransitionSearchSortToken(BaseModel):
    """One resolved sort column for ``search_transitions``."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Column name used in ORDER BY")
    direction: Literal["asc", "desc"] = Field(description="Sort direction")


class TransitionSearchStats(BaseModel):
    """Aggregate stats for the current filter (omit when include_stats is false)."""

    model_config = ConfigDict(extra="forbid")

    total_rows: int
    hard_reject_count: int
    hard_reject_ratio: float | None = None
    overall_quality: dict[str, Any] = Field(
        description="avg/min/max overall_quality over the filtered rows (nulls when empty set)",
    )
    component_averages: dict[str, Any] = Field(
        description="Named averages for BPM/harmonic/energy/spectral/groove/timbral components",
    )
    fx_type_top: list[dict[str, Any]] = Field(
        description="Top fx_type values with counts (non-null fx_type only)",
    )


class TransitionQualityGuardrail(BaseModel):
    """Feasibility guardrail for target transition quality in current filtered slice."""

    model_config = ConfigDict(extra="forbid")

    target_quality: float | None = Field(
        default=None,
        description="Requested target quality from caller (0-1), if provided",
    )
    max_overall_quality: float | None = Field(
        default=None,
        description="Maximum overall_quality observed in current filtered slice",
    )
    meets_target: bool | None = Field(
        default=None,
        description="Whether max_overall_quality >= target_quality (null when no target)",
    )
    non_reject_rows_at_or_above_target: int | None = Field(
        default=None,
        description="Count of non-hard-reject rows with overall_quality >= target_quality",
    )
    message: str = Field(description="Human-readable guidance for next action")


class SearchTransitionsResult(BaseModel):
    """Structured MCP output for ``search_transitions`` (pagination, filters, projection)."""

    model_config = ConfigDict(extra="forbid")

    rows: list[dict[str, Any]] = Field(
        description="Result rows; shape follows ``fields.selected`` (default: id only)",
    )
    offset: int
    limit: int
    returned: int
    total: int
    next_offset: int | None = Field(
        default=None,
        description="Offset value to pass for the next page, or null when at end",
    )
    truncated: bool = Field(description="True when more rows exist after this page")
    sort: list[TransitionSearchSortToken]
    filters_applied: dict[str, Any] = Field(
        description="Normalized filter object applied to the query (may be empty)",
    )
    fields: dict[str, Any] = Field(
        description=(
            "Projection metadata: always ``selected`` and ``excluded``; when "
            "``include_field_catalog`` is true also ``available``, ``groups``, ``include_macros``"
        ),
    )
    stats: TransitionSearchStats | None = Field(
        default=None,
        description="Aggregate stats; null when include_stats is false",
    )
    filter_operators: list[str] | None = Field(
        default=None,
        description="Allowed filter operator names (only if include_field_catalog is true)",
    )
    quality_guardrail: TransitionQualityGuardrail | None = Field(
        default=None,
        description="Target-quality feasibility summary for the current filtered slice",
    )


class GetSetCheatSheetResult(BaseModel):
    """Printable booth reference from ``get_set_cheat_sheet``."""

    set_id: int
    version: str | None = Field(
        default=None,
        description="Resolved version label when provided",
    )
    cheat_sheet: str = Field(
        description="Full text with newline separators (same as cheat_sheet_lines joined)",
    )
    cheat_sheet_lines: list[str] = Field(
        description=(
            "Same content as one line per entry. Prefer this field in JSON-heavy UIs "
            "where strings show literal \\n instead of line breaks."
        ),
    )


ListSetsResult.model_rebuild()
SetVersionResult.model_rebuild()
TransitionScoreResult.model_rebuild()
SetArcPreview.model_rebuild()
SetTemplateSlotRow.model_rebuild()
SetTemplateEntry.model_rebuild()
GetSetTemplatesResult.model_rebuild()
GetSetCheatSheetResult.model_rebuild()
TransitionSearchSortToken.model_rebuild()
TransitionSearchStats.model_rebuild()
TransitionQualityGuardrail.model_rebuild()
SearchTransitionsResult.model_rebuild()
