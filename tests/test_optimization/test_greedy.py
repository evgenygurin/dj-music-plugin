"""Tests for GreedyChainBuilder with candidate pre-filter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.entities.audio.features import TrackFeatures
from app.optimization.greedy import GreedyChainBuilder
from app.transition.scorer import TransitionScorer


def _feat(bpm: float, key_code: int, lufs: float) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)


def test_greedy_skips_hard_rejected_pairs() -> None:
    """Pre-filter reduces scorer calls: incompatible pairs are skipped.

    3 tracks: A(120) compatible with B(122), not with C(135, diff=15>10).
    Without filter: scorer called 2 times (B and C from A).
    With filter: only 1 time (only B).
    compute_fitness is mocked to avoid extra scorer calls.
    """
    mock_result = MagicMock()
    mock_result.hard_reject = False
    mock_result.overall = 0.8

    mock_scorer = MagicMock(spec=TransitionScorer)
    mock_scorer.score.return_value = mock_result

    # A=120, B=122 (diff=2 ✓), C=135 (diff=15 ✗ hard reject)
    tracks = [_feat(120.0, 0, -10.0), _feat(122.0, 1, -10.0), _feat(135.0, 0, -10.0)]
    track_ids = [1, 2, 3]

    with patch("app.optimization.greedy.compute_fitness", return_value=0.5):
        builder = GreedyChainBuilder(mock_scorer)
        result = builder.optimize(tracks, track_ids)

    # Результат содержит все 3 трека
    assert set(result.track_order) == {1, 2, 3}
    assert len(result.track_order) == 3
    # With filter: scorer called fewer times than without (not 4, but <= 3)
    # A->B (1 call) + B->C (1 call, only candidate from adjacency or fallback)
    # Total <= 3 calls (without filter: A->B + A->C + B->A + B->C = 4)
    assert mock_scorer.score.call_count <= 3


def test_greedy_scores_valid_pairs() -> None:
    """Greedy calls scorer for valid pairs in the while loop."""
    mock_result = MagicMock()
    mock_result.hard_reject = False
    mock_result.overall = 0.8

    mock_scorer = MagicMock(spec=TransitionScorer)
    mock_scorer.score.return_value = mock_result

    tracks = [_feat(130.0, 0, -10.0), _feat(132.0, 1, -11.0)]
    track_ids = [1, 2]

    with patch("app.optimization.greedy.compute_fitness", return_value=0.5):
        builder = GreedyChainBuilder(mock_scorer)
        result = builder.optimize(tracks, track_ids)

    mock_scorer.score.assert_called()
    assert set(result.track_order) == {1, 2}


def test_greedy_fallback_when_all_filtered() -> None:
    """When all candidates are filtered out, greedy picks any remaining track."""
    mock_scorer = MagicMock(spec=TransitionScorer)
    tracks = [_feat(120.0, 0, -10.0), _feat(135.0, 0, -10.0), _feat(150.0, 0, -10.0)]
    track_ids = [1, 2, 3]

    with patch("app.optimization.greedy.compute_fitness", return_value=0.0):
        builder = GreedyChainBuilder(mock_scorer)
        result = builder.optimize(tracks, track_ids)

    assert len(result.track_order) == 3
    assert set(result.track_order) == {1, 2, 3}
