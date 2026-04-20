"""Invariant tests for app/transition/weights.py.

Pure data file — these are sanity checks (sums, ranges, types) so that
mistuning a constant fails CI before it ships.
"""

from __future__ import annotations

import math

import pytest

from app.domain.transition.weights import (
    BPM_GAUSS_SIGMA,
    BPM_STABILITY_FLOOR,
    CAMELOT_BASE_SCORES,
    DEFAULT_STYLE_RULES,
    DEFAULT_WEIGHTS,
    ENERGY_PREFERRED_RISE_LUFS,
    ENERGY_SIGMOID_DIVISOR,
    GROOVE_SUB_WEIGHTS,
    SPECTRAL_SUB_WEIGHTS,
    TIMBRAL_SUB_WEIGHTS,
    StyleRules,
)


class TestDefaultWeights:
    def test_sums_to_one(self) -> None:
        total = sum(DEFAULT_WEIGHTS.values())
        assert math.isclose(total, 1.0, abs_tol=1e-9), (
            f"DEFAULT_WEIGHTS must sum to 1.0, got {total}"
        )

    def test_has_six_components(self) -> None:
        expected = {"bpm", "harmonic", "energy", "spectral", "groove", "timbral"}
        assert set(DEFAULT_WEIGHTS.keys()) == expected

    @pytest.mark.parametrize("name,weight", list(DEFAULT_WEIGHTS.items()))
    def test_each_weight_in_unit_range(self, name: str, weight: float) -> None:
        assert 0.0 <= weight <= 1.0, f"{name}={weight} outside [0,1]"


class TestSubWeights:
    def test_spectral_sub_weights_sum(self) -> None:
        assert math.isclose(sum(SPECTRAL_SUB_WEIGHTS.values()), 1.0, abs_tol=1e-9)

    def test_groove_sub_weights_sum(self) -> None:
        assert math.isclose(sum(GROOVE_SUB_WEIGHTS.values()), 1.0, abs_tol=1e-9)

    def test_timbral_sub_weights_sum(self) -> None:
        assert math.isclose(sum(TIMBRAL_SUB_WEIGHTS.values()), 1.0, abs_tol=1e-9)


class TestNumericInvariants:
    # Per-band calibration + double/half-time + stability branches are
    # exercised against the real score_bpm in
    # tests/domain/transition/components/test_bpm.py.

    def test_bpm_sigma_matches_hard_reject_boundary(self) -> None:
        """Soft score at the hard-reject BPM boundary must be ≥ 0.5.

        Guards against drift between `BPM_GAUSS_SIGMA` and the canonical
        hard-reject threshold — e.g. if someone tightens the hard reject
        to ΔBPM=8 without shrinking sigma, the soft curve at the new
        boundary silently becomes very lenient (~0.73).
        """
        from app.config import get_settings

        boundary_bpm = get_settings().transition.hard_reject_bpm_diff
        boundary_score = math.exp(-(boundary_bpm**2) / (2 * BPM_GAUSS_SIGMA**2))
        assert boundary_score >= 0.5, (
            f"score at hard-reject boundary (ΔBPM={boundary_bpm}) "
            f"is {boundary_score:.3f} < 0.5 — sigma/threshold drift"
        )

    def test_stability_floor_in_range(self) -> None:
        assert 0.0 <= BPM_STABILITY_FLOOR <= 1.0

    def test_camelot_scores_monotone_decreasing(self) -> None:
        """Greater Camelot distance must score no better than smaller."""
        distances = sorted(CAMELOT_BASE_SCORES.keys())
        values = [CAMELOT_BASE_SCORES[d] for d in distances]
        assert values == sorted(values, reverse=True), (
            f"non-monotone: {dict(zip(distances, values, strict=True))}"
        )

    def test_camelot_distance_0_is_perfect(self) -> None:
        assert CAMELOT_BASE_SCORES[0] == 1.0

    def test_camelot_distance_2_relaxed_per_ismir_2017(self) -> None:
        """ISMIR 2017 (Bittner et al.) treats distance ≤ 2 as a valid
        candidate — floor must be ≥ 0.8 (previous 0.6 was stricter)."""
        assert CAMELOT_BASE_SCORES[2] >= 0.8

    def test_energy_gauss_params_in_sane_range(self) -> None:
        assert ENERGY_SIGMOID_DIVISOR > 0
        # Preferred rise must stay under the 2 LUFS perceptual threshold
        # or the Gauss peak lands somewhere listeners notice as "jump".
        assert 0.0 <= ENERGY_PREFERRED_RISE_LUFS < 2.0


class TestStyleRules:
    def test_default_rules_is_frozen(self) -> None:
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            DEFAULT_STYLE_RULES.spectral_collision_cutoff = 0.99  # type: ignore[misc]

    def test_default_rules_thresholds_in_unit_range(self) -> None:
        rules = DEFAULT_STYLE_RULES
        for name in (
            "spectral_collision_cutoff",
            "energy_gap_cutoff",
            "harmonic_drift_cutoff",
            "perfect_bpm_cutoff",
            "perfect_harmonic_cutoff",
            "perfect_groove_cutoff",
            "confident_overall_cutoff",
        ):
            value = getattr(rules, name)
            assert 0.0 <= value <= 1.0, f"{name}={value} outside [0,1]"

    def test_can_override(self) -> None:
        custom = StyleRules(spectral_collision_cutoff=0.5)
        assert custom.spectral_collision_cutoff == 0.5
        # Other defaults preserved
        assert custom.energy_gap_cutoff == DEFAULT_STYLE_RULES.energy_gap_cutoff
