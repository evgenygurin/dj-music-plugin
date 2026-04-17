"""Pydantic view models for resource payloads.

These sit alongside entity CRUD views (TrackView, PlaylistView, ...).
They describe the *shape* of resource responses — purely presentation
DTOs, never persisted. All fields are chosen to match the JSON the LLM
receives: no hidden SQLAlchemy attributes, no ORM leakage.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ── Track resources ─────────────────────────────────────────────


class TrackAuditView(_Base):
    track_id: int
    passed: bool
    violations: list[str] = Field(default_factory=list)
    score: float = Field(..., ge=0.0, le=1.0)
    criteria_checked: int


class SuggestNextView(_Base):
    from_track_id: int
    limit: int
    energy_direction: str | None
    candidates: list[dict[str, Any]]


class SuggestReplacementView(_Base):
    set_id: int
    position: int
    removed_track_id: int | None
    candidates: list[dict[str, Any]]


# ── Playlist resources ──────────────────────────────────────────


class PlaylistAuditView(_Base):
    playlist_id: int
    total_tracks: int
    passed: int
    failed: int
    per_track: list[dict[str, Any]]


# ── Set resources ───────────────────────────────────────────────


class SetSummaryView(_Base):
    set_id: int
    name: str
    template_name: str | None
    version_count: int
    latest_version_id: int | None
    latest_quality_score: float | None


class SetTracksView(_Base):
    set_id: int
    version_id: int
    tracks: list[dict[str, Any]]


class SetTransitionsView(_Base):
    set_id: int
    version_id: int
    transitions: list[dict[str, Any]]


class SetCheatsheetView(_Base):
    set_id: int
    version_id: int
    lines: list[dict[str, Any]]


class SetNarrativeView(_Base):
    set_id: int
    version_id: int
    narrative: str
    phases: list[dict[str, Any]]


class SetReviewView(_Base):
    set_id: int
    version_id: int
    quality_score: float
    weak_transitions: list[dict[str, Any]]
    hard_conflicts: list[dict[str, Any]]


class SetCompareView(_Base):
    set_id: int
    version_a: dict[str, Any]
    version_b: dict[str, Any]
    delta: float
    changed_positions: list[int]


# ── Transition resources ────────────────────────────────────────


class TransitionScoreView(_Base):
    from_track_id: int
    to_track_id: int
    overall: float
    hard_reject: bool
    reject_reason: str | None
    components: dict[str, float]


class TransitionExplainView(_Base):
    from_track_id: int
    to_track_id: int
    overall: float
    narrative: str
    suggestions: list[str]


# ── Transition history ──────────────────────────────────────────


class BestPairsView(_Base):
    limit: int
    pairs: list[dict[str, Any]]


class TransitionHistoryView(_Base):
    limit: int
    entries: list[dict[str, Any]]


# ── Session resources ───────────────────────────────────────────


class SessionDraftView(_Base):
    session_id: str
    tracks: list[dict[str, Any]]
    target_duration_ms: int | None
    template_name: str | None
    last_mutation_at: str | None


class SessionToolHistoryView(_Base):
    session_id: str
    entries: list[dict[str, Any]]


class SessionEnergyTrendView(_Base):
    last_n: int
    samples: list[float]


# ── Schema introspection ────────────────────────────────────────


class SchemaIndexView(_Base):
    entities: list[str]


class SchemaEntityView(_Base):
    name: str
    operations: list[str]
    presets: dict[str, list[str]]
    default_preset: str
    searchable_fields: list[str]
    filterable_fields: dict[str, list[str]]
    sortable_fields: list[str]
    relations: list[str]
    view_schema: dict[str, Any]
    filter_schema: dict[str, Any]
    create_schema: dict[str, Any]
    update_schema: dict[str, Any]


class SchemaProviderIndexView(_Base):
    providers: list[str]


class SchemaProviderView(_Base):
    name: str
    entities_supported: list[str]
    operations: dict[str, bool]
