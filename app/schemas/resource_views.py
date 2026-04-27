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
    # ``reason`` distinguishes "no candidates" cases — audit observation
    # O-3. Empty ``candidates`` accompanied by ``reason=None`` means the
    # suggestion ran cleanly and simply found nothing; a non-None
    # ``reason`` flags a missing-data condition (no transitions logged
    # for this track, energy filter ate everything, etc.).
    reason: str | None = None


class SuggestReplacementView(_Base):
    set_id: int
    position: int
    removed_track_id: int | None
    candidates: list[dict[str, Any]]
    reason: str | None = None


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


# ── Reference blobs ─────────────────────────────────────────────


class CamelotKeyView(_Base):
    code: int
    notation: str
    name: str
    position: int  # 1-12 wheel position
    mode: str  # "A" (minor) or "B" (major)
    compat_edges: list[dict[str, Any]]  # [{target_code, target_notation, distance}]


class CamelotWheelView(_Base):
    total: int
    wheel_size: int
    keys: list[CamelotKeyView]


class SubgenreFeatureView(_Base):
    name: str
    weight: float
    ideal: float
    tolerance: float


class SubgenreProfileView(_Base):
    subgenre: str
    catch_all_penalty: float
    is_catch_all: bool
    features: list[SubgenreFeatureView]


class SubgenresView(_Base):
    total: int
    catch_all: list[str]
    profiles: list[SubgenreProfileView]


class TemplateSlotView(_Base):
    position: float
    target_mood: str | None
    energy_lufs: float
    bpm_min: float
    bpm_max: float
    duration_ms: int
    flexibility: float


class TemplateView(_Base):
    name: str
    duration_min: int
    description: str
    slots: list[TemplateSlotView]


class TemplatesView(_Base):
    total: int
    templates: list[TemplateView]


class AuditRuleView(_Base):
    name: str
    severity: str
    issue: str
    thresholds: dict[str, float | int | str]


class AuditRulesView(_Base):
    total: int
    rules: list[AuditRuleView]
