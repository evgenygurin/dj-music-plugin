"""Regression tests pinning the Gauss-around-+0.5-LUFS shape of score_energy.

These tests guard the 2026-04-20 calibration:
- Identical loudness must score ~1.0 (prior sigmoid-centred-at-0 gave 0.5 —
  a bug that punished stable-energy peak-time sets).
- Peak lives at delta = ENERGY_PREFERRED_RISE_LUFS (+0.5 LUFS).
- Drops cost more than equal-magnitude rises (asymmetry around +0.5).
"""

from __future__ import annotations

import pytest

from app.domain.transition.components.energy import score_energy
from app.domain.transition.features import TrackFeatures


def _f(lufs: float) -> TrackFeatures:
    """Minimal TrackFeatures with only the fields score_energy needs."""
    return TrackFeatures(integrated_lufs=lufs)


def test_identical_loudness_scores_near_one() -> None:
    """Gauss peak is close to delta=0 → equal LUFS must score > 0.95.

    Under the prior sigmoid centred at 0, this returned 0.5 — the core
    bug the calibration fixes.
    """
    assert score_energy(_f(-10.0), _f(-10.0)) > 0.95


def test_preferred_rise_gives_peak_score() -> None:
    """Peak of the Gauss is at +0.5 LUFS (ENERGY_PREFERRED_RISE_LUFS)."""
    assert score_energy(_f(-10.0), _f(-9.5)) == pytest.approx(1.0, abs=1e-6)


def test_drop_penalised_more_than_equal_magnitude_rise() -> None:
    """Asymmetry: a +2 LUFS rise must outscore a -2 LUFS drop.

    Follows from shifting the Gauss peak to +0.5 LUFS rather than 0.
    """
    ref = _f(-10.0)
    rise_2 = score_energy(ref, _f(-8.0))
    drop_2 = score_energy(ref, _f(-12.0))
    assert rise_2 > drop_2


@pytest.mark.parametrize(
    "delta,expected",
    [
        (-4.0, 0.33),
        (-2.0, 0.71),
        (0.0, 0.99),
        (0.5, 1.00),
        (2.0, 0.88),
        (4.0, 0.51),
    ],
)
def test_gauss_shape_value_table(delta: float, expected: float) -> None:
    """Full calibration value table from docs/transition-scoring.md § S_energy.

    Pins sigma=ENERGY_SIGMOID_DIVISOR=3.0 and peak=ENERGY_PREFERRED_RISE_LUFS=0.5.
    A regression in either constant will surface through at least one row.
    """
    assert score_energy(_f(-10.0), _f(-10.0 + delta)) == pytest.approx(expected, abs=0.02)


@pytest.mark.xfail(
    reason=(
        "Fallback returns 0.5 (legacy), but equal-loudness now scores ~0.99 "
        "under the Gauss formula — a bias against tracks with missing LUFS "
        "features in GA selection. Follow-up: align fallback with "
        "ENERGY_PREFERRED_RISE_LUFS behaviour (peak value)."
    ),
    strict=True,
)
def test_missing_lufs_fallback_consistent_with_equal_loudness() -> None:
    """Missing LUFS should map to the same score as equal-loudness (~1.0).

    Currently returns 0.5 (a legacy sentinel from the sigmoid era).
    Marked xfail to lock in the discrepancy until the follow-up fix lands.
    """
    fallback = score_energy(TrackFeatures(), TrackFeatures())
    equal_loudness = score_energy(_f(-10.0), _f(-10.0))
    assert abs(fallback - equal_loudness) < 0.1
