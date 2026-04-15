"""Tests for GreedyChainBuilder with candidate pre-filter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.entities.audio.features import TrackFeatures
from app.optimization.greedy import GreedyChainBuilder
from app.transition.scorer import TransitionScorer


def _feat(bpm: float, key_code: int, lufs: float) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)


def test_greedy_skips_hard_rejected_pairs() -> None:
    """Pre-filter сокращает вызовы scorer: несовместимые пары не оцениваются.

    3 трека: A(120) совместим с B(122), но не с C(135, diff=15>10).
    Без фильтра в while-цикле scorer вызывается 2 раза (B и C от A).
    С фильтром — только 1 раз (только B).
    compute_fitness замокирован, чтобы не добавлять лишние вызовы scorer.
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
    # С фильтром scorer вызывается меньше раз чем без (не 4, а ≤ 3)
    # A→B (1 вызов) + B→C (1 вызов, единственный кандидат из adjacency или fallback)
    # Итого ≤ 3 вызовов (без фильтра было бы A→B + A→C + B→A + B→C = 4)
    assert mock_scorer.score.call_count <= 3


def test_greedy_scores_valid_pairs() -> None:
    """Greedy вызывает scorer для валидных пар в while-цикле."""
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
    """Если все кандидаты отфильтрованы — greedy берёт любой оставшийся."""
    mock_scorer = MagicMock(spec=TransitionScorer)
    tracks = [_feat(120.0, 0, -10.0), _feat(135.0, 0, -10.0), _feat(150.0, 0, -10.0)]
    track_ids = [1, 2, 3]

    with patch("app.optimization.greedy.compute_fitness", return_value=0.0):
        builder = GreedyChainBuilder(mock_scorer)
        result = builder.optimize(tracks, track_ids)

    assert len(result.track_order) == 3
    assert set(result.track_order) == {1, 2, 3}
