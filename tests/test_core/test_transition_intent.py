"""Tests for app/core/transition_intent.py — infer_intent v1 + v2."""

from __future__ import annotations

import pytest

from dj_music.core.constants import SetTemplate
from dj_music.transition.intent import (
    INTENT_WEIGHT_MODIFIERS,
    TransitionIntent,
    infer_intent,
)


class TestInferIntentBackwardCompat:
    """v1 — no template argument, historical 0.20/0.85 cutoffs."""

    def test_early_set_position_ramps_up(self) -> None:
        assert infer_intent(set_position=0.10, energy_delta_lufs=0.0) == (TransitionIntent.RAMP_UP)

    def test_late_set_position_cools_down(self) -> None:
        assert infer_intent(set_position=0.90, energy_delta_lufs=0.0) == (
            TransitionIntent.COOL_DOWN
        )

    def test_mid_set_maintain(self) -> None:
        assert infer_intent(set_position=0.50, energy_delta_lufs=0.5) == (
            TransitionIntent.MAINTAIN
        )

    def test_strong_positive_energy_ramps_up(self) -> None:
        assert infer_intent(set_position=0.50, energy_delta_lufs=3.0) == (TransitionIntent.RAMP_UP)

    def test_strong_negative_energy_cools_down(self) -> None:
        assert infer_intent(set_position=0.50, energy_delta_lufs=-3.0) == (
            TransitionIntent.COOL_DOWN
        )


class TestInferIntentTemplateAware:
    """v2 — per-template phase boundaries."""

    def test_warm_up_30_treats_mid_as_warmup(self) -> None:
        # WARM_UP_30 phases: warmup_end=0.50 → position 0.40 still warming up
        assert infer_intent(0.40, 0.0, template=SetTemplate.WARM_UP_30) == (
            TransitionIntent.RAMP_UP
        )

    def test_peak_hour_60_treats_early_as_peak(self) -> None:
        # PEAK_HOUR_60 phases: warmup_end=0.10 → position 0.15 already in peak
        assert infer_intent(0.15, 0.0, template=SetTemplate.PEAK_HOUR_60) == (
            TransitionIntent.MAINTAIN
        )

    def test_closing_60_treats_mid_as_cooling(self) -> None:
        # CLOSING_60 phases: peak_end=0.50 → position 0.55 already cooling
        assert infer_intent(0.55, 0.0, template=SetTemplate.CLOSING_60) == (
            TransitionIntent.COOL_DOWN
        )

    def test_no_template_falls_back_to_default_phases(self) -> None:
        # Position 0.15 with no template → RAMP_UP (default warmup_end=0.20)
        assert infer_intent(0.15, 0.0) == TransitionIntent.RAMP_UP
        # Position 0.15 with PEAK_HOUR_60 → MAINTAIN (warmup_end=0.10)
        assert infer_intent(0.15, 0.0, template=SetTemplate.PEAK_HOUR_60) == (
            TransitionIntent.MAINTAIN
        )

    @pytest.mark.parametrize("template", list(SetTemplate))
    def test_every_template_has_phase_table_entry(self, template: SetTemplate) -> None:
        """Each SetTemplate must produce a sensible result without raising."""
        result = infer_intent(0.5, 0.0, template=template)
        assert isinstance(result, TransitionIntent)


class TestIntentWeightModifiers:
    @pytest.mark.parametrize("intent", list(TransitionIntent))
    def test_modifier_sums_to_one(self, intent: TransitionIntent) -> None:
        weights = INTENT_WEIGHT_MODIFIERS[intent]
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9, f"{intent}={total}"

    @pytest.mark.parametrize("intent", list(TransitionIntent))
    def test_modifier_has_six_components(self, intent: TransitionIntent) -> None:
        expected = {"bpm", "harmonic", "energy", "spectral", "groove", "timbral"}
        assert set(INTENT_WEIGHT_MODIFIERS[intent].keys()) == expected
