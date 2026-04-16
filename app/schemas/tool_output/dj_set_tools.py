"""Structured MCP outputs for DJ set tools: commit, arc preview, templates, scoring."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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
