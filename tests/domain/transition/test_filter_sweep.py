from __future__ import annotations

from app.domain.transition.builders import build_filter_sweep
from app.domain.transition.neural_mix import NeuralMixTransition
from app.domain.transition.picker import pick_neural_mix
from app.domain.transition.recipe import LEVEL_SILENT, LEVEL_UNITY
from app.domain.transition.score import TransitionScore
from app.domain.transition.subgenre_rules import SubgenrePairType
from app.shared.features import TrackFeatures


class TestFilterSweepBuilder:
    def test_builds_correct_number_of_keyframes(self):
        kfs, fx = build_filter_sweep(32)
        assert len(kfs) > 0
        assert len(fx) == 0

    def test_a_fades_out(self):
        kfs, _ = build_filter_sweep(32)
        a_last = [k for k in kfs if k.deck == "A" and k.bar == 32]
        for k in a_last:
            assert k.level_db == LEVEL_SILENT

    def test_b_fades_in(self):
        kfs, _ = build_filter_sweep(32)
        b_last = [k for k in kfs if k.deck == "B" and k.bar == 32]
        for k in b_last:
            assert k.level_db == LEVEL_UNITY


class TestPickerFilterSweep:
    def test_acid_pair_selects_filter_sweep(self):
        score = TransitionScore(
            bpm=0.8,
            energy=0.7,
            drums=0.7,
            bass=0.6,
            harmonics=0.5,
            vocals=0.5,
            overall=0.65,
        )
        fa = TrackFeatures()
        fb = TrackFeatures()
        decision = pick_neural_mix(
            score,
            fa,
            fb,
            section_context=None,
            subgenre_pair=SubgenrePairType.ACID_PAIR,
            intent=None,
        )
        assert decision.transition == NeuralMixTransition.FILTER_SWEEP
        assert decision.confidence == 0.85
