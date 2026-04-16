"""Pydantic response models for MCP tool structured output.

FastMCP 3+ auto-generates output_schema from return type annotations,
helping LLMs parse responses reliably.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class WeakSpot(BaseModel):
    """A weak transition point in a set arc."""

    position: int
    score: float
    reason: str = ""


class SetArcPreview(BaseModel):
    """Preview of a set's energy arc and quality."""

    score: float = Field(description="Overall arc quality 0-1")
    energy_arc: list[float]
    bpm_arc: list[float]
    weak_spots: list[WeakSpot]
    recommendation: str
    missing_track_ids: list[int]
