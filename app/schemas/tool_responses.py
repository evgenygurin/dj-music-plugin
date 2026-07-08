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
    # ``bool`` must appear BEFORE ``int`` in the union — Pydantic v2 picks the
    # first compatible type, and bool is a subclass of int. Without an explicit
    # ``bool`` slot, ``distinct(field="variable_tempo")`` coerced ``False`` to
    # ``0`` on the way out, contradicting the group_by branch (where ``Any``
    # preserves the real Python type). See round-10 manual test.
    value: (
        int | float | list[dict[str, Any]] | list[bool | int | float | str | None] | dict[str, Any]
    )


class ScorePoolResult(BaseModel):
    track_ids: list[int]
    pairs: list[dict[str, Any]] = Field(
        description=(
            "[{a, b, overall, bpm, harmonics, energy, bass, drums, vocals}]; "
            "component fields absent when components=false, list truncated "
            "to N*top_k best outgoing pairs when top_k is set"
        )
    )
    hard_rejects: int = 0
    # Response-size controls (top_k / components) can shrink ``pairs`` far
    # below the full matrix; keep the pre-truncation count visible so a
    # capped response never silently reads as "scored everything".
    total_scored_pairs: int = Field(
        default=0,
        description=(
            "Directed pairs actually scored (full matrix minus missing-feature "
            "ids) BEFORE top_k truncation. len(pairs) < total_scored_pairs "
            "means the response was capped by top_k."
        ),
    )
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
    algorithm: Literal["ga", "greedy", "constructive"]
    generations: int = 0


class PlaylistSyncResult(BaseModel):
    playlist_id: int
    direction: Literal["pull", "push", "diff"]
    applied: list[dict[str, Any]] = Field(default_factory=list)
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)


class TransitionCandidate(BaseModel):
    track_id: int = Field(description="Candidate track ID")
    title: str = ""
    overall: float = Field(ge=0.0, le=1.0, description="Aggregate transition quality")
    bpm: float | None = None
    key: str | None = None
    energy: float | None = None
    mood: str | None = None
    hard_reject: bool = False
    reject_reason: str | None = None
    best_transition: str | None = Field(
        default=None, description="Selected Neural Mix preset name"
    )


class TransitionCandidatesResult(BaseModel):
    from_track_id: int = Field(description="Source track being scored against")
    total_analyzed: int = Field(description="Tracks in the analyzed library")
    candidates: list[TransitionCandidate] = Field(
        default_factory=list,
        description="Sorted by overall descending, hard rejects excluded",
    )
    missing_features: bool = Field(
        default=False,
        description="True when from_track itself has no audio features",
    )


class UnlockNamespaceResult(BaseModel):
    namespace: str
    status: Literal["unlocked", "locked", "status"]
    enabled_tools: list[str] = Field(default_factory=list)
