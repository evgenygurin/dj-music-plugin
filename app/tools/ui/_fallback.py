"""Fallback payloads + client-detection helper for Prefab UI tools.

Each UI tool returns a ``prefab_ui.components.Column`` (or ``PrefabApp``)
when the client advertises Prefab support; otherwise it returns a Pydantic
fallback model defined here so the LLM still sees a structured payload.

The single ``supports_ui(ctx)`` helper isolates the extension name, so a
rename in FastMCP 3.3+ only needs one edit.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel, Field

# Canonical MCP Apps extension ID (SEP-1865). Re-exported from FastMCP so
# a future rename in upstream stays in one place.
try:
    from fastmcp.apps.config import UI_EXTENSION_ID
except ImportError:  # pragma: no cover — fastmcp[apps] extra missing
    UI_EXTENSION_ID = "io.modelcontextprotocol/ui"


def supports_ui(ctx: Any) -> bool:
    """Return True when the MCP client supports the Prefab UI extension.

    Falls back to ``False`` when the context does not expose extension
    negotiation (older FastMCP, test stubs, CLI probes) — the caller then
    returns a Pydantic fallback payload instead of a UI component tree.
    """
    check = getattr(ctx, "client_supports_extension", None)
    if callable(check):
        try:
            return bool(check(UI_EXTENSION_ID))
        except Exception:
            return False
    return False


# ── Fallback Pydantic models ──────────────────────────────────────────


class EnergyPoint(BaseModel):
    position: int
    lufs: float | None = None


class TrackRow(BaseModel):
    position: int
    track_id: int
    title: str | None = None
    bpm: float | None = None
    key_code: int | None = None
    camelot: str | None = None
    lufs: float | None = None
    mood: str | None = None


class TransitionEdge(BaseModel):
    position: int
    from_track_id: int
    to_track_id: int
    overall: float | None = None
    hard_reject: bool | None = None


class SetViewFallback(BaseModel):
    set_id: int
    name: str | None = None
    template_name: str | None = None
    version_id: int | None = None
    quality_score: float | None = None
    tracks: list[TrackRow] = Field(default_factory=list)
    energy_arc: list[EnergyPoint] = Field(default_factory=list)
    transitions: list[TransitionEdge] = Field(default_factory=list)


class TransitionScoreFallback(BaseModel):
    from_track_id: int
    to_track_id: int
    components: dict[str, float] = Field(default_factory=dict)
    overall: float
    hard_reject: bool
    reject_reason: str | None = None
    style: str | None = None
    style_bars: int | None = None
    style_reason: str | None = None


class AuditTrackRow(BaseModel):
    track_id: int
    title: str | None = None
    passed: bool
    violations: list[str] = Field(default_factory=list)


class LibraryAuditFallback(BaseModel):
    playlist_id: int | None = None
    total_tracks: int
    passed: int
    failed: int
    coverage: float
    per_track: list[AuditTrackRow] = Field(default_factory=list)
    subgenre_distribution: dict[str, int] = Field(default_factory=dict)
    # ``truncated`` distinguishes "audited 23k tracks, all in" from
    # "audited the first N of 23k tracks because the library exceeds
    # the cap". None when scope is per-playlist (bounded already).
    truncated: bool | None = None
    library_size: int | None = None
    limit: int | None = None


class ScorePoolCell(BaseModel):
    a: int
    b: int
    overall: float
    hard_reject: bool = False


class ScorePoolMatrixFallback(BaseModel):
    track_ids: list[int]
    cells: list[ScorePoolCell] = Field(default_factory=list)
    hard_rejects: int = 0


class DashboardFallback(BaseModel):
    total_tracks: int
    analyzed_tracks: int
    coverage: float
    bpm_histogram: dict[str, int] = Field(default_factory=dict)
    mood_distribution: dict[str, int] = Field(default_factory=dict)
    camelot_distribution: dict[str, int] = Field(default_factory=dict)


class CamelotWheelSlot(BaseModel):
    camelot: str
    key_code: int
    track_count: int


class CamelotWheelFallback(BaseModel):
    playlist_id: int | None = None
    total_tracks: int
    slots: list[CamelotWheelSlot] = Field(default_factory=list)


class RenderStudioFallback(BaseModel):
    version_id: int
    n_tracks: int = 0
    target_bpm: float | None = None
    beatgrid: list[dict[str, Any]] = Field(default_factory=list)
    job: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


class ControlCenterFallback(BaseModel):
    version_id: int
    set_id: int | None = None
    source_playlist_id: int | None = None
    set_name: str | None = None
    quality_score: float | None = None
    n_tracks: int = 0
    # library overview
    total_tracks: int = 0
    analyzed_tracks: int = 0
    coverage: float = 0.0
    bpm_histogram: dict[str, int] = Field(default_factory=dict)
    mood_distribution: dict[str, int] = Field(default_factory=dict)
    # current set/version
    tracks: list[dict[str, Any]] = Field(default_factory=list)
    energy_arc: list[dict[str, Any]] = Field(default_factory=list)
    # render sub-block
    beatgrid: list[dict[str, Any]] = Field(default_factory=list)
    job: dict[str, Any] | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


T = TypeVar("T", bound=BaseModel)


def fallback_or(cls: type[T], data: Any) -> T:  # noqa: UP047
    """Validate a dict/mapping into a fallback Pydantic model.

    Keeps call sites one-liners:

        return fallback_or(SetViewFallback, payload)
    """
    return cls.model_validate(data)
