import pytest

from app.domain.analysis.beatgrid import BeatGrid, BeatPosition


def test_beat_position_carries_phase_and_downbeat() -> None:
    beat = BeatPosition(time_s=1.25, index=8, is_downbeat=True)
    assert beat.time_s == 1.25
    assert beat.is_downbeat


def test_beatgrid_validates_monotonic_positions_and_tempo() -> None:
    beats = (BeatPosition(0.0, 0), BeatPosition(0.47, 1))
    grid = BeatGrid(bpm=128.0, beats=beats, beats_per_bar=4, phase_s=0.0)
    assert grid.beat_period_s == pytest.approx(60 / 128)
    with pytest.raises(ValueError, match="monotonic"):
        BeatGrid(bpm=128, beats=(BeatPosition(1, 0), BeatPosition(0, 1)))
