"""Tests for TransitionScorer.score_with_candidates() integration."""

import pytest

from dj_music.schemas.audio import TrackFeatures
from dj_music.transition.scorer import TransitionScorer


@pytest.fixture
def scorer() -> TransitionScorer:
    return TransitionScorer()


def _make_track(**kwargs: object) -> TrackFeatures:
    defaults = {
        "bpm": 128.0,
        "key_code": 14,  # 8A
        "integrated_lufs": -8.0,
        "spectral_centroid_hz": 3000.0,
        "energy_mean": 0.6,
        "onset_rate": 4.0,
        "kick_prominence": 0.5,
    }
    defaults.update(kwargs)
    return TrackFeatures(**defaults)  # type: ignore[arg-type]


# ── score_with_candidates: no candidate data → same as score() ──


def test_no_candidate_data_falls_back(scorer: TransitionScorer) -> None:
    """Without candidate data, score_with_candidates should behave like score()."""
    a = _make_track()
    b = _make_track(bpm=130.0)

    normal = scorer.score(a, b)
    with_candidates = scorer.score_with_candidates(a, b)

    assert normal.overall == pytest.approx(with_candidates.overall)
    assert normal.hard_reject == with_candidates.hard_reject


# ── score_with_candidates: hard reject from candidate data ──


def test_candidate_bpm_hard_reject(scorer: TransitionScorer) -> None:
    """Pre-computed BPM distance above threshold should hard-reject."""
    a = _make_track()
    b = _make_track()

    result = scorer.score_with_candidates(a, b, candidate_bpm_distance=15.0)

    assert result.hard_reject is True
    assert "BPM" in (result.reject_reason or "")


def test_candidate_key_hard_reject(scorer: TransitionScorer) -> None:
    """Pre-computed Camelot distance at threshold should hard-reject."""
    a = _make_track()
    b = _make_track()

    result = scorer.score_with_candidates(a, b, candidate_key_distance=5)

    assert result.hard_reject is True
    assert "Camelot" in (result.reject_reason or "")


def test_candidate_energy_hard_reject(scorer: TransitionScorer) -> None:
    """Pre-computed energy delta above threshold should hard-reject."""
    a = _make_track()
    b = _make_track()

    result = scorer.score_with_candidates(a, b, candidate_energy_delta=7.0)

    assert result.hard_reject is True
    assert "Energy" in (result.reject_reason or "")


# ── score_with_candidates: valid candidate data ──


def test_candidate_data_within_limits(scorer: TransitionScorer) -> None:
    """Pre-computed distances within limits should produce a valid score."""
    a = _make_track()
    b = _make_track(bpm=130.0)

    result = scorer.score_with_candidates(
        a,
        b,
        candidate_bpm_distance=2.0,
        candidate_key_distance=0,
        candidate_energy_delta=0.0,
    )

    assert result.hard_reject is False
    assert result.overall > 0.0
    assert 0.0 <= result.overall <= 1.0


def test_candidate_partial_data(scorer: TransitionScorer) -> None:
    """Only some candidate data provided — remaining should fall back to features."""
    a = _make_track(bpm=128.0, key_code=14, integrated_lufs=-8.0)
    b = _make_track(bpm=130.0, key_code=14, integrated_lufs=-9.0)

    # Provide only BPM distance, let key and energy use features
    result = scorer.score_with_candidates(a, b, candidate_bpm_distance=2.0)

    assert result.hard_reject is False
    assert result.overall > 0.0


# ── Consistency check: same result regardless of path ──


def test_consistent_scoring(scorer: TransitionScorer) -> None:
    """Same inputs should give same component scores via both methods."""
    a = _make_track(bpm=128.0, key_code=14, integrated_lufs=-8.0)
    b = _make_track(bpm=130.0, key_code=12, integrated_lufs=-9.0)

    normal = scorer.score(a, b)
    # Pre-computed distances matching actual distances
    with_candidates = scorer.score_with_candidates(
        a,
        b,
        candidate_bpm_distance=2.0,  # |128 - 130|
        candidate_key_distance=1,  # 8A → 7A
        candidate_energy_delta=1.0,  # |-8 - (-9)|
    )

    # Both should not be rejected
    assert not normal.hard_reject
    assert not with_candidates.hard_reject

    # Component scores computed from features should be the same
    assert normal.bpm == pytest.approx(with_candidates.bpm)
    assert normal.harmonic == pytest.approx(with_candidates.harmonic)
    assert normal.energy == pytest.approx(with_candidates.energy)
    assert normal.spectral == pytest.approx(with_candidates.spectral)
    assert normal.groove == pytest.approx(with_candidates.groove)
    assert normal.overall == pytest.approx(with_candidates.overall)
