"""Tests for TransitionSelector — the new transition FX selection engine."""

from app.core.constants import NeuralMixCrossfaderFX, SectionType
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import EQPlan, TransitionRecipe
from app.transition.score import TransitionScore
from app.transition.section_context import SectionContext
from app.transition.selector import TransitionSelector


def _score(**kwargs: float) -> TransitionScore:
    defaults = dict(
        bpm=0.8, harmonic=0.8, energy=0.8, spectral=0.8, groove=0.8, timbral=0.8, overall=0.8
    )
    defaults.update(kwargs)
    return TransitionScore(**defaults)


def _features(**kwargs: object) -> TrackFeatures:
    return TrackFeatures(bpm=128.0, integrated_lufs=-10.0, **kwargs)  # type: ignore[arg-type]


def test_select_returns_neural_mix_fx():
    selector = TransitionSelector()
    fx = selector.select(_score(), _features(), _features())
    assert isinstance(fx, NeuralMixCrossfaderFX)


def test_hard_reject_returns_fade():
    selector = TransitionSelector()
    score = TransitionScore(hard_reject=True, reject_reason="bpm too different")
    fx = selector.select(score, _features(), _features())
    assert fx == NeuralMixCrossfaderFX.NEURAL_MIX_FADE


def test_drum_only_high_groove_returns_drum_cut():
    selector = TransitionSelector()
    score = _score(groove=0.95, overall=0.9)
    ctx = SectionContext(from_section=SectionType.INTRO, to_section=SectionType.OUTRO)
    fx = selector.select(score, _features(), _features(), section_context=ctx)
    assert fx == NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_CUT


def test_build_recipe_returns_transition_recipe():
    selector = TransitionSelector()
    recipe = selector.build_recipe(_score(), _features(), _features())
    assert isinstance(recipe, TransitionRecipe)
    assert recipe.fx_type is not None
    assert recipe.bars >= 0
    assert len(recipe.steps) > 0


def test_build_recipe_bpm_warning():
    selector = TransitionSelector()
    fa = TrackFeatures(bpm=128.0, integrated_lufs=-10.0)
    fb = TrackFeatures(bpm=133.0, integrated_lufs=-10.0)
    recipe = selector.build_recipe(_score(), fa, fb)
    assert any("BPM" in w or "delta" in w.lower() for w in recipe.warnings)


def test_all_seven_fx_reachable_via_steps():
    """Every NeuralMixCrossfaderFX must produce a non-empty step sequence."""
    from app.transition.recipe_steps import build_steps_for_fx

    for fx in NeuralMixCrossfaderFX:
        steps, eq = build_steps_for_fx(fx, 16)
        assert len(steps) > 0, f"{fx} produced no steps"
        assert isinstance(eq, EQPlan)
