"""Export data models — pure domain dataclasses, no I/O."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExportTrack:
    """Track data needed for export."""

    position: int
    title: str
    artist: str
    duration_ms: int
    file_path: str
    bpm: float | None = None
    key_camelot: str | None = None
    energy_lufs: float | None = None
    cue_points: list[dict[str, Any]] = field(default_factory=list)
    saved_loops: list[dict[str, Any]] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)
    mood: str | None = None
    notes: str | None = None
    eq_settings: dict[str, Any] | None = None
    # P3 enrichment fields
    mood_confidence: float | None = None
    rms_dbfs: float | None = None
    true_peak_db: float | None = None
    crest_factor_db: float | None = None
    danceability: float | None = None
    hp_ratio: float | None = None
    dominant_phrase_bars: int | None = None
    variable_tempo: bool | None = None
    audio_features: dict[str, Any] | None = None  # full features for JSON guide


@dataclass
class ExportTransition:
    """Transition data between two tracks."""

    from_position: int
    to_position: int
    score: float | None = None
    bpm_delta: float | None = None
    key_distance: int | None = None
    energy_delta: float | None = None
    transition_type: str | None = None
    notes: str | None = None
    transition_bars: int | None = None
    djay_transition: str | None = None
    recipe_steps: list[dict[str, Any]] | None = None
    eq_plan: dict[str, Any] | None = None
    rescue_move: str | None = None


@dataclass
class SetExportData:
    """Complete set data for export."""

    name: str
    version_label: str | None = None
    quality_score: float | None = None
    tracks: list[ExportTrack] = field(default_factory=list)
    transitions: list[ExportTransition] = field(default_factory=list)


@dataclass
class RekordboxOptions:
    """Configurable inclusion flags for Rekordbox export."""

    include_cue_points: bool = True
    include_saved_loops: bool = True
    include_beatgrid: bool = True
    include_sections: bool = False
