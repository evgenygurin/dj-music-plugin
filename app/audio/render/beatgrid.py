"""Render-layer adapter for audio :class:`BeatGrid` analysis.

This module is the bridge between the cheap library-level beatgrid
produced by ``app.audio.analyzers.beatgrid`` and the render pipeline
that needs a concrete bar/beat timeline. It is intentionally
lightweight: no I/O, no librosa calls in the hot path — the heavy
work (autocorrelation, beat detection) already happened during
library analysis and is cached on the track.

The :func:`beatgrid_to_render_entry` helper converts an audio
beatgrid into the existing ``BeatgridEntry`` dataclass consumed by
the domain/render layer, preserving the canonical column names. The
legacy file-based ``BeatgridEntry`` in ``app.audio.deep`` keeps
working unchanged.

Cheap library analysis vs. deeper mixing analysis:
    Library beatgrid → fast, runs on every track during import.
    Render beatgrid  → adds per-track kick-phase + refinement on top.
    This module does NOT trigger deeper analysis — it just adapts
    the library result to the render schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.audio.core.tempo import (
    BeatGrid,
    TempoCurvePoint,
    TempoHypothesis,
    beatgrid_from_arrays,
)

# Re-export the audio builder so render callers can construct a grid
# from raw analysis features without re-importing the analyzer.
__all__ = [
    "BeatgridBuilder",
    "beatgrid_to_render_entry",
    "beatgrid_from_arrays",
    "BeatGrid",
    "TempoCurvePoint",
    "TempoHypothesis",
]


@dataclass(frozen=True, slots=True)
class BeatgridBuilder:
    """Lightweight builder for :class:`BeatGrid` instances from feature dicts.

    Used by callers that already have a flat feature dict (e.g. the
    pipeline result for the ``beatgrid`` analyzer) and want a typed
    grid without going through the full analyzer pipeline.
    """

    bpm: float
    bpm_confidence: float
    bpm_stability: float
    variable_tempo: bool
    beats_per_bar: int = 4

    def build(
        self,
        *,
        beat_times_s: tuple[float, ...] = (),
        downbeat_times_s: tuple[float, ...] = (),
        bar_times_s: tuple[float, ...] = (),
        phase_s: float = 0.0,
        hypotheses: tuple[TempoHypothesis, ...] = (),
        tempo_curve: tuple[TempoCurvePoint, ...] = (),
        phrase_boundaries_s: tuple[float, ...] = (),
    ) -> BeatGrid:
        return beatgrid_from_arrays(
            bpm=self.bpm,
            bpm_confidence=self.bpm_confidence,
            bpm_stability=self.bpm_stability,
            variable_tempo=self.variable_tempo,
            beats_per_bar=self.beats_per_bar,
            beat_times_s=beat_times_s,
            downbeat_times_s=downbeat_times_s,
            bar_times_s=bar_times_s,
            phase_s=phase_s,
            hypotheses=hypotheses,
            tempo_curve=tempo_curve,
            phrase_boundaries_s=phrase_boundaries_s,
        )

    @classmethod
    def from_features(cls, features: dict[str, Any]) -> BeatgridBuilder:
        """Build a :class:`BeatgridBuilder` from a flat feature dict.

        Accepts the raw output of the ``beatgrid`` analyzer
        (``features["beatgrid"]`` is the JSON-serialized grid) or the
        top-level BPM analyzer output. Missing fields default to
        the techno 4/4 at the dominant hypothesis.
        """
        bpm = float(features.get("bpm", 0.0) or 0.0)
        return cls(
            bpm=bpm,
            bpm_confidence=float(features.get("bpm_confidence", 0.0) or 0.0),
            bpm_stability=float(features.get("bpm_stability", 0.0) or 0.0),
            variable_tempo=bool(features.get("variable_tempo", False)),
            beats_per_bar=int(features.get("beats_per_bar", 4) or 4),
        )


def beatgrid_to_render_entry(grid: BeatGrid, track_id: int) -> dict[str, Any]:
    """Project a :class:`BeatGrid` into the render-engine's per-track row.

    The render engine persists one row per track in ``beatgrid.json``
    with at least these fields:

        track_id, trim_start_s, phase_ms, bpm_measured, beats_per_bar

    The audio beatgrid only knows the library-level timeline, so
    ``trim_start_s`` defaults to the first beat (the on-grid anchor)
    and ``phase_ms`` is the sub-beat phase of that anchor converted
    to milliseconds. The render engine can refine these later via
    the existing kick-phase pipeline without losing information.
    """
    if grid.n_beats == 0:
        return {
            "track_id": track_id,
            "trim_start_s": 0.0,
            "phase_ms": 0.0,
            "bpm_measured": grid.bpm,
            "bpm_confidence": grid.bpm_confidence,
            "bpm_stability": grid.bpm_stability,
            "variable_tempo": grid.variable_tempo,
            "beats_per_bar": grid.beats_per_bar,
            "n_beats": 0,
            "n_bars": 0,
            "first_beat_s": 0.0,
        }
    first_beat = grid.first_beat_s()
    period_s = grid.beat_period_s
    phase_ms = round((grid.phase_s * 1000.0), 3) if period_s > 0 else 0.0
    return {
        "track_id": track_id,
        "trim_start_s": round(first_beat, 6),
        "phase_ms": phase_ms,
        "bpm_measured": round(grid.bpm, 4),
        "bpm_confidence": round(grid.bpm_confidence, 4),
        "bpm_stability": round(grid.bpm_stability, 4),
        "variable_tempo": grid.variable_tempo,
        "beats_per_bar": grid.beats_per_bar,
        "n_beats": grid.n_beats,
        "n_bars": grid.n_bars,
        "first_beat_s": round(first_beat, 6),
    }
