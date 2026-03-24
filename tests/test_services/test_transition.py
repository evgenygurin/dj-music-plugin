"""Tests for TransitionScorer — 5-component scoring with hard constraints."""

import pytest

from app.services.transition import TrackFeatures, TransitionScorer


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


# ── Hard constraints ─────────────────────────────────


def test_hard_reject_bpm(scorer: TransitionScorer) -> None:
    a = _make_track(bpm=128.0)
    b = _make_track(bpm=142.0)  # diff = 14 > 10
    result = scorer.score(a, b)
    assert result.hard_reject is True
    assert result.overall == 0.0
    assert "BPM" in (result.reject_reason or "")


def test_hard_reject_camelot(scorer: TransitionScorer) -> None:
    a = _make_track(key_code=0)  # 1A
    b = _make_track(key_code=12)  # 7A — distance=6 >= 5
    result = scorer.score(a, b)
    assert result.hard_reject is True
    assert "Camelot" in (result.reject_reason or "")


def test_hard_reject_energy(scorer: TransitionScorer) -> None:
    a = _make_track(integrated_lufs=-6.0)
    b = _make_track(integrated_lufs=-14.0)  # gap = 8 > 6
    result = scorer.score(a, b)
    assert result.hard_reject is True
    assert "Energy" in (result.reject_reason or "")


def test_no_hard_reject_within_limits(scorer: TransitionScorer) -> None:
    a = _make_track(bpm=128.0, key_code=14, integrated_lufs=-8.0)
    b = _make_track(bpm=130.0, key_code=12, integrated_lufs=-9.0)
    result = scorer.score(a, b)
    assert result.hard_reject is False
    assert result.overall > 0.0


# ── BPM scoring ──────────────────────────────────────


def test_bpm_same_tempo(scorer: TransitionScorer) -> None:
    a = _make_track(bpm=128.0)
    b = _make_track(bpm=128.0)
    result = scorer.score(a, b)
    assert result.bpm > 0.95  # almost perfect


def test_bpm_close_tempo(scorer: TransitionScorer) -> None:
    a = _make_track(bpm=128.0)
    b = _make_track(bpm=130.0)
    result = scorer.score(a, b)
    assert result.bpm > 0.7


def test_bpm_double_time(scorer: TransitionScorer) -> None:
    """Double-time awareness: 128 → 64 should be close."""
    a = _make_track(bpm=128.0)
    b = _make_track(bpm=64.0)
    result = scorer.score(a, b)
    assert result.bpm > 0.9


# ── Harmonic scoring ─────────────────────────────────


def test_harmonic_same_key(scorer: TransitionScorer) -> None:
    a = _make_track(key_code=14)
    b = _make_track(key_code=14)
    result = scorer.score(a, b)
    assert result.harmonic > 0.9


def test_harmonic_adjacent_key(scorer: TransitionScorer) -> None:
    a = _make_track(key_code=14)  # 8A
    b = _make_track(key_code=12)  # 7A — adjacent
    result = scorer.score(a, b)
    assert result.harmonic > 0.7


def test_harmonic_far_key(scorer: TransitionScorer) -> None:
    a = _make_track(key_code=14)  # 8A
    b = _make_track(key_code=6)  # 4A — distance=4
    result = scorer.score(a, b)
    assert result.harmonic < 0.3


# ── Overall scoring ──────────────────────────────────


def test_overall_between_0_and_1(scorer: TransitionScorer) -> None:
    a = _make_track()
    b = _make_track(bpm=130.0, key_code=16)  # slightly different
    result = scorer.score(a, b)
    assert 0.0 <= result.overall <= 1.0


def test_identical_tracks_high_score(scorer: TransitionScorer) -> None:
    a = _make_track()
    b = _make_track()
    result = scorer.score(a, b)
    assert result.overall > 0.7


def test_missing_features_neutral(scorer: TransitionScorer) -> None:
    """Missing features should give neutral (0.5) component scores."""
    a = TrackFeatures()  # all None
    b = TrackFeatures()
    result = scorer.score(a, b)
    assert not result.hard_reject
    assert abs(result.overall - 0.5) < 0.1


def test_custom_weights(scorer: TransitionScorer) -> None:
    """Custom weights should change the overall score."""
    a = _make_track()
    b = _make_track(bpm=130.0)

    default_scorer = TransitionScorer()
    bpm_heavy_scorer = TransitionScorer(
        weights={"bpm": 0.8, "harmonic": 0.05, "energy": 0.05, "spectral": 0.05, "groove": 0.05}
    )

    default_result = default_scorer.score(a, b)
    bpm_result = bpm_heavy_scorer.score(a, b)

    # BPM-heavy scorer should differ from default
    assert default_result.overall != bpm_result.overall
