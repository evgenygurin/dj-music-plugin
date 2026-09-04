"""Tests for the render-layer beatgrid adapter.

The adapter is the bridge between the cheap library-level
:class:`BeatGrid` and the render engine's per-track row schema.
It must not do any heavy work (no librosa, no onset detection) —
it only projects typed fields. The tests pin that contract.
"""

from __future__ import annotations

import pytest

from app.audio.core.tempo import BeatGrid, TempoHypothesis, beatgrid_from_arrays
from app.audio.render.beatgrid import (
    BeatgridBuilder,
    beatgrid_to_render_entry,
)


def _grid(
    *,
    bpm: float = 128.0,
    beats: tuple[float, ...] = (0.0, 0.46875, 0.9375, 1.40625),
    confidence: float = 0.9,
    stability: float = 0.95,
) -> BeatGrid:
    return beatgrid_from_arrays(
        bpm=bpm,
        bpm_confidence=confidence,
        bpm_stability=stability,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=beats,
        downbeat_times_s=(0.0,),
        bar_times_s=(0.0,),
        phase_s=0.0,
        hypotheses=(TempoHypothesis(bpm=bpm, confidence=confidence, octave_preference=1.0),),
    )


def test_beatgrid_builder_round_trip() -> None:
    builder = BeatgridBuilder(
        bpm=128.0,
        bpm_confidence=0.9,
        bpm_stability=0.95,
        variable_tempo=False,
    )
    grid = builder.build(
        beat_times_s=(0.0, 0.5, 1.0, 1.5),
        downbeat_times_s=(0.0,),
        bar_times_s=(0.0,),
        phase_s=0.0,
    )
    assert isinstance(grid, BeatGrid)
    assert grid.bpm == 128.0
    assert grid.n_beats == 4
    assert grid.hypotheses == ()


def test_beatgrid_builder_from_features() -> None:
    builder = BeatgridBuilder.from_features(
        {
            "bpm": 130.0,
            "bpm_confidence": 0.85,
            "bpm_stability": 0.9,
            "variable_tempo": False,
            "beats_per_bar": 4,
        }
    )
    assert builder.bpm == 130.0
    assert builder.bpm_confidence == 0.85


def test_beatgrid_builder_from_features_handles_missing() -> None:
    builder = BeatgridBuilder.from_features({})
    assert builder.bpm == 0.0
    assert builder.beats_per_bar == 4
    assert builder.variable_tempo is False


def test_beatgrid_to_render_entry_with_beats() -> None:
    grid = _grid()
    row = beatgrid_to_render_entry(grid, track_id=42)
    assert row["track_id"] == 42
    assert row["bpm_measured"] == 128.0
    assert row["bpm_confidence"] == pytest.approx(0.9, abs=1e-4)
    assert row["bpm_stability"] == pytest.approx(0.95, abs=1e-4)
    assert row["variable_tempo"] is False
    assert row["beats_per_bar"] == 4
    assert row["n_beats"] == 4
    assert row["n_bars"] == 1
    assert row["trim_start_s"] == 0.0
    assert row["first_beat_s"] == 0.0


def test_beatgrid_to_render_entry_empty_beats() -> None:
    grid = beatgrid_from_arrays(
        bpm=0.0,
        bpm_confidence=0.0,
        bpm_stability=0.0,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(),
        downbeat_times_s=(),
        bar_times_s=(),
        phase_s=0.0,
    )
    row = beatgrid_to_render_entry(grid, track_id=7)
    assert row["track_id"] == 7
    assert row["bpm_measured"] == 0.0
    assert row["n_beats"] == 0
    assert row["n_bars"] == 0
    assert row["trim_start_s"] == 0.0


def test_beatgrid_to_render_entry_phase_ms_with_offset() -> None:
    """Phase in seconds must convert to ms in the render row."""
    grid = beatgrid_from_arrays(
        bpm=128.0,
        bpm_confidence=0.9,
        bpm_stability=0.95,
        variable_tempo=False,
        beats_per_bar=4,
        beat_times_s=(0.123, 0.6, 1.1, 1.6),
        downbeat_times_s=(0.123,),
        bar_times_s=(0.123,),
        phase_s=0.123,
    )
    row = beatgrid_to_render_entry(grid, track_id=1)
    assert row["trim_start_s"] == pytest.approx(0.123, abs=1e-6)
    assert row["phase_ms"] == pytest.approx(123.0, abs=1e-3)
