"""Integration test: full selector pipeline from score to recipe JSON."""

from app.core.constants import NeuralMixCrossfaderFX
from app.entities.audio.features import TrackFeatures
from app.transition.recipe import TransitionRecipe
from app.transition.score import TransitionScore
from app.transition.selector import TransitionSelector


def _features(bpm: float = 128.0, lufs: float = -10.0) -> TrackFeatures:
    return TrackFeatures(bpm=bpm, integrated_lufs=lufs)


def _score(**kwargs: float) -> TransitionScore:
    defaults = dict(
        bpm=0.85,
        harmonic=0.80,
        energy=0.80,
        spectral=0.80,
        groove=0.75,
        timbral=0.75,
        overall=0.80,
    )
    defaults.update(kwargs)
    return TransitionScore(**defaults)


def test_full_pipeline_returns_drum_swap_for_good_groove():
    selector = TransitionSelector()
    score = _score(groove=0.80, overall=0.80)
    recipe = selector.build_recipe(score, _features(), _features())
    assert recipe.fx_type == NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP
    assert recipe.bars > 0


def test_full_pipeline_serialise_deserialise():
    selector = TransitionSelector()
    recipe = selector.build_recipe(_score(), _features(), _features())
    json_str = recipe.to_json()
    restored = TransitionRecipe.from_json(json_str)
    assert restored is not None
    assert restored.fx_type == recipe.fx_type
    assert restored.bars == recipe.bars
    assert len(restored.steps) == len(recipe.steps)


def test_hard_reject_gives_fade_recipe():
    selector = TransitionSelector()
    score = TransitionScore(hard_reject=True, reject_reason="bpm gap 15")
    recipe = selector.build_recipe(score, _features(), _features())
    assert recipe.fx_type == NeuralMixCrossfaderFX.NEURAL_MIX_FADE
    assert recipe.confidence < 0.7
