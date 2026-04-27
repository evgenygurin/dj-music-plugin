"""Structured-output Pydantic models for all v2 MCP tools.

Each tool returns a model from this file; FastMCP auto-generates
``output_schema`` in the tool metadata so LLM clients parse results reliably.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class EntityListResult(BaseModel):
    entity: str = Field(description="Entity type name (e.g., 'track', 'playlist')")
    items: list[dict[str, Any]] = Field(default_factory=list)
    total: int | None = Field(default=None, description="Total rows matching (if with_total)")
    next_cursor: str | None = Field(default=None)


class EntityGetResult(BaseModel):
    entity: str
    id: int
    data: dict[str, Any]


class EntityCreateResult(BaseModel):
    entity: str
    data: dict[str, Any] | list[dict[str, Any]]
    meta: dict[str, Any] = Field(default_factory=dict)


class EntityUpdateResult(BaseModel):
    entity: str
    id: int
    data: dict[str, Any]


class EntityDeleteResult(BaseModel):
    entity: str
    id: int
    deleted: bool


class AggregateResult(BaseModel):
    entity: str
    operation: Literal["count", "distinct", "histogram", "min_max", "sum", "avg"]
    field: str | None = None
    group_by: str | None = None
    value: int | float | list[dict[str, Any]] | list[int | float | str | None] | dict[str, Any]


class ScorePoolResult(BaseModel):
    track_ids: list[int]
    pairs: list[dict[str, Any]] = Field(
        description="[{a, b, overall, bpm, harmonic, energy, spectral, groove, timbral}]"
    )
    hard_rejects: int = 0
    # Audit iter 44 (T-42): track which ids had no scoring features.
    # Without this field, calling ``transition_score_pool`` with stale
    # / non-existent ids returned ``pairs=[]`` silently — caller
    # couldn't tell typo apart from "tracks aren't analyzed yet".
    missing_track_ids: list[int] = Field(
        default_factory=list,
        description=(
            "Track IDs that were dropped because they have no scoring features "
            "(track_audio_features_computed row absent). When this is non-empty "
            "and ``pairs`` is empty, the caller is hitting un-analysed / typo'd "
            "ids — not a bug in scoring."
        ),
    )


class SequenceOptimizeResult(BaseModel):
    track_order: list[int]
    quality_score: float
    algorithm: Literal["ga", "greedy"]
    generations: int = 0


class PlaylistSyncResult(BaseModel):
    playlist_id: int
    direction: Literal["pull", "push", "diff"]
    applied: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class UnlockNamespaceResult(BaseModel):
    namespace: str
    status: Literal["unlocked", "locked", "status"]
    enabled_tools: list[str] = Field(default_factory=list)
