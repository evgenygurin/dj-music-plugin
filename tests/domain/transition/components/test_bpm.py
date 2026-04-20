"""Regression tests for BPM_GAUSS_SIGMA=10 calibration + score_bpm branches.

Prior sigma=3.0 gave score_bpm(delta=5) = 0.25, punishing the normal
Pioneer DJ / Mixed In Key sync workflow (3-5 BPM is precisely the
"within +/-6% pitch range" band). Calibrated against Kim et al. ISMIR 2020.
"""

from __future__ import annotations

import math

import pytest

from app.domain.transition.components.bpm import score_bpm
from app.domain.transition.features import TrackFeatures
from app.domain.transition.weights import BPM_GAUSS_SIGMA


def _f(
    bpm: float = 128.0,
    *,
    stability: float = 1.0,
    confidence: float = 1.0,
    variable_tempo: bool = False,
) -> TrackFeatures:
    """Stable-BPM TrackFeatures — isolates the pure Gauss curve by
    neutralising stability / confidence / variable_tempo branches."""
    return TrackFeatures(
        bpm=bpm,
        bpm_stability=stability,
        bpm_confidence=confidence,
        variable_tempo=variable_tempo,
    )


@pytest.mark.parametrize(
    "dbpm,expected",
    [
        (0, 1.00),
        (2, 0.98),
        (3, 0.96),
        (5, 0.88),
        (8, 0.73),
        (10, 0.61),
    ],
)
def test_score_bpm_gauss_shape(dbpm: float, expected: float) -> None:
    """End-to-end score_bpm must match docs § S_bpm table on stable tracks.

    A regression from sigma=10 to sigma=3 (or another value) will fail
    at least one row. Regression in stability/confidence multipliers
    will also fire because this test drives them at 1.0 (no penalty path).
    """
    assert score_bpm(_f(128.0), _f(128.0 + dbpm)) == pytest.approx(expected, abs=0.02)


def test_sync_safe_range_scores_above_0_85() -> None:
    """3-5 BPM (Pioneer CDJ ±6% pitch range) must stay above 0.85 end-to-end."""
    for dbpm in (3, 4, 5):
        score = score_bpm(_f(128.0), _f(128.0 + dbpm))
        assert score > 0.85, f"ΔBPM={dbpm} scored {score:.3f}, expected > 0.85"


def test_double_time_detected_as_perfect_match() -> None:
    """bpm_distance picks the minimum over direct / double / half, so
    128 vs 256 (double) must score ~1.0 despite a raw 128 BPM gap."""
    assert score_bpm(_f(128.0), _f(256.0)) == pytest.approx(1.0, abs=0.01)


def test_half_time_detected_as_perfect_match() -> None:
    """Symmetric: 128 vs 64 (half) must score ~1.0."""
    assert score_bpm(_f(128.0), _f(64.0)) == pytest.approx(1.0, abs=0.01)


def test_low_stability_pulls_score_down() -> None:
    """stability < BPM_STABILITY_FLOOR clamps the multiplier to the floor."""
    stable = score_bpm(_f(128.0, stability=1.0), _f(128.0, stability=1.0))
    wobbly = score_bpm(_f(128.0, stability=0.3), _f(128.0, stability=0.3))
    assert wobbly < stable
    # Floor is 0.7 — score must not fall below ~0.7 even at stability=0.0
    floored = score_bpm(_f(128.0, stability=0.0), _f(128.0, stability=0.0))
    assert floored >= 0.69  # 1.0 * 0.7 stability floor


def test_missing_bpm_returns_neutral() -> None:
    """Unknown tempo = neutral 0.5 (documented fallback)."""
    assert score_bpm(TrackFeatures(), _f(128.0)) == 0.5


def test_hard_reject_boundary_has_math_consistent_soft_score() -> None:
    """ΔBPM=10 (hard-reject threshold) on the raw Gauss is ~0.61.

    This is the pure-math guard — if BPM_GAUSS_SIGMA changes without
    touching the hard-reject threshold, the soft score at the boundary
    drifts and the optimizer suddenly treats near-rejected pairs
    as 'tight'. Keeps sigma and hard_reject_bpm_diff in lockstep.
    """
    boundary = math.exp(-100 / (2 * BPM_GAUSS_SIGMA**2))
    assert boundary == pytest.approx(0.61, abs=0.02)
