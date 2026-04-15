from unittest.mock import MagicMock

from app.entities.audio.features import TrackFeatures
from app.optimization.genetic import GeneticAlgorithm
from app.transition.models import TransitionScore
from app.transition.scorer import TransitionScorer


def _feat(bpm: float, key_code: int, lufs: float) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, key_code=key_code, integrated_lufs=lufs)


def _mock_scorer() -> MagicMock:
    mock_score = MagicMock(spec=TransitionScore)
    mock_score.hard_reject = False
    mock_score.overall = 0.5
    mock_score.bpm = 0.8
    mock_score.harmonic = 0.7
    mock_score.energy = 0.6
    mock_score.spectral = 0.5
    mock_score.groove = 0.5
    mock_score.timbral = 0.5
    scorer = MagicMock(spec=TransitionScorer)
    scorer.score.return_value = mock_score
    return scorer


def test_ga_returns_all_tracks() -> None:
    """GA returns all tracks in the result."""
    scorer = _mock_scorer()
    tracks = [_feat(130.0, 0, -10.0), _feat(131.0, 1, -11.0), _feat(132.0, 0, -10.5)]
    track_ids = [1, 2, 3]
    ga = GeneticAlgorithm(scorer, population_size=10, max_generations=5)
    result = ga.optimize(tracks, track_ids)
    assert len(result.track_order) == 3
    assert set(result.track_order) == {1, 2, 3}
    assert result.algorithm == "ga"


def test_ga_with_compatible_tracks() -> None:
    """GA with pre-filter compatible tracks returns a valid result."""
    scorer = _mock_scorer()
    tracks = [_feat(130.0, 0, -10.0), _feat(131.0, 1, -11.0)]
    track_ids = [10, 20]
    ga = GeneticAlgorithm(scorer, population_size=6, max_generations=3)
    result = ga.optimize(tracks, track_ids)
    assert set(result.track_order) == {10, 20}
    assert result.quality_score >= 0.0
