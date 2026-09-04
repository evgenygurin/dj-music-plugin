from app.domain.analysis.beatgrid import BeatGrid, BeatPosition
from app.domain.mixing.alignment import AlignmentEngine, AlignmentRequest


def grid(phase: float = 0.0) -> BeatGrid:
    return BeatGrid(
        120, tuple(BeatPosition(i * 0.5, i, i % 4 == 0) for i in range(64)), phase_s=phase
    )


def test_alignment_accepts_small_phase_and_phrase_error() -> None:
    result = AlignmentEngine().align(
        grid(), grid(0.02), AlignmentRequest(8, phase_tolerance_s=0.05)
    )
    assert result.accepted
    assert result.beat_error_s <= 0.05


def test_alignment_rejects_large_phase_error() -> None:
    result = AlignmentEngine().align(
        grid(), grid(0.2), AlignmentRequest(8, phase_tolerance_s=0.05)
    )
    assert not result.accepted
    assert result.reason == "beat_phase_tolerance"
