"""Tests for preview_arc pure function."""

from __future__ import annotations

from app.entities.audio.features import TrackFeatures
from app.optimization.preview import PreviewResult, preview_arc
from app.transition.scorer import TransitionScorer


def _make_features(bpm: float, lufs: float, key_code: int = 0) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, integrated_lufs=lufs, key_code=key_code)


def _make_scorer() -> TransitionScorer:
    return TransitionScorer()


def test_preview_arc_returns_correct_structure():
    """preview_arc returns PreviewResult with all required fields."""
    scorer = _make_scorer()
    features_map = {
        1: _make_features(132.0, -11.5),
        2: _make_features(133.0, -11.0),
        3: _make_features(134.0, -10.5),
    }
    result = preview_arc(scorer, features_map, track_ids=[1, 2, 3])

    assert isinstance(result, PreviewResult)
    assert 0.0 <= result.score <= 1.0
    assert len(result.energy_arc) == 3
    assert len(result.bpm_arc) == 3
    assert isinstance(result.weak_spots, list)
    assert isinstance(result.recommendation, str)
    assert len(result.recommendation) > 0


def test_preview_arc_energy_arc_matches_lufs():
    """energy_arc values correspond to track LUFS values."""
    scorer = _make_scorer()
    lufs_values = [-13.0, -12.0, -11.0, -10.0]
    features_map = {i: _make_features(132.0, lufs) for i, lufs in enumerate(lufs_values)}
    result = preview_arc(scorer, features_map, track_ids=list(range(4)))

    assert result.energy_arc == lufs_values


def test_preview_arc_bpm_arc_matches_bpm():
    """bpm_arc values correspond to track BPM values."""
    scorer = _make_scorer()
    bpm_values = [130.0, 132.0, 134.0, 136.0]
    features_map = {i: _make_features(bpm, -11.0) for i, bpm in enumerate(bpm_values)}
    result = preview_arc(scorer, features_map, track_ids=list(range(4)))

    assert result.bpm_arc == bpm_values


def test_preview_arc_weak_spots_are_valid_positions():
    """weak_spots contains positions 0..n-2 (transition positions)."""
    scorer = _make_scorer()
    # Create a deliberately bad transition: big BPM jump
    features_map = {
        0: _make_features(120.0, -13.0, key_code=0),
        1: _make_features(150.0, -8.0, key_code=12),  # huge BPM + key jump
        2: _make_features(122.0, -13.0, key_code=0),
    }
    result = preview_arc(scorer, features_map, track_ids=[0, 1, 2])

    for pos in result.weak_spots:
        assert 0 <= pos < 2, f"weak_spot {pos} out of range for 3-track set"


def test_preview_arc_missing_features_skipped():
    """Tracks missing from features_map are excluded gracefully."""
    scorer = _make_scorer()
    features_map = {
        1: _make_features(132.0, -11.5),
        # track_id=2 intentionally missing
        3: _make_features(134.0, -10.5),
    }
    result = preview_arc(scorer, features_map, track_ids=[1, 2, 3])
    # Should return result for the 2 tracks that have features
    assert len(result.energy_arc) == 2
    assert len(result.bpm_arc) == 2


def test_preview_arc_single_track():
    """Single track returns score 1.0 (no transitions to score)."""
    scorer = _make_scorer()
    features_map = {1: _make_features(132.0, -11.5)}
    result = preview_arc(scorer, features_map, track_ids=[1])

    assert result.score == 1.0
    assert result.weak_spots == []


def test_preview_arc_recommendation_mentions_score():
    """Recommendation string mentions the score or quality level."""
    scorer = _make_scorer()
    features_map = {i: _make_features(132.0 + i, -11.0) for i in range(5)}
    result = preview_arc(scorer, features_map, track_ids=list(range(5)))

    # Recommendation should contain numerical or qualitative score mention
    assert any(
        word in result.recommendation.lower()
        for word in ["score", "quality", "good", "weak", "strong", "transition"]
    )
