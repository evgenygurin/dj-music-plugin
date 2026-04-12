"""Invariant tests for app/transition/weights.py.

Pure data file — these are sanity checks (sums, ranges, types) so that
mistuning a constant fails CI before it ships.
"""

from __future__ import annotations

import math

import pytest

from dj_music.transition.weights import (
    BPM_GAUSS_SIGMA,
    BPM_STABILITY_FLOOR,
    DEFAULT_STYLE_RULES,
    DEFAULT_WEIGHTS,
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
    def test_bpm_sigma_positive(self) -> None:
        assert BPM_GAUSS_SIGMA > 0

    def test_stability_floor_in_range(self) -> None:
        assert 0.0 <= BPM_STABILITY_FLOOR <= 1.0


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
