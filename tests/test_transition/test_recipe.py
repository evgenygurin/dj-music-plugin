"""Tests for EQPlan, RecipeStep, and TransitionRecipe."""

import json

from app.core.constants import NeuralMixCrossfaderFX
from app.transition.recipe import EQPlan, RecipeStep, TransitionRecipe
from app.transition.types import StemAction


def test_eq_plan_defaults():
    plan = EQPlan()
    assert plan.low == "stem"
    assert plan.mid == "stem"
    assert plan.high == "stem"


def test_eq_plan_round_trip():
    plan = EQPlan(low="cut", mid="filter", high="stem")
    assert EQPlan.from_dict(plan.to_dict()) == plan


def test_recipe_step_round_trip():
    step = RecipeStep(
        bar=4,
        deck="A",
        action="fade out drums",
        stem="drums",
        stem_action=StemAction.FADE_OUT,
    )
    d = step.to_dict()
    restored = RecipeStep.from_dict(d)
    assert restored == step


def test_recipe_step_from_dict_invalid_deck():
    assert RecipeStep.from_dict({"bar": 0, "deck": "C", "action": "x"}) is None


def test_recipe_step_from_dict_bool_bar():
    assert RecipeStep.from_dict({"bar": True, "deck": "A", "action": "x"}) is None


def test_transition_recipe_round_trip():
    step = RecipeStep(
        bar=0,
        deck="B",
        action="bring in B drums",
        stem="drums",
        stem_action=StemAction.FADE_IN,
    )
    recipe = TransitionRecipe(
        fx_type=NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP,
        bars=16,
        steps=(step,),
        warnings=("key clash",),
        confidence=0.85,
        rescue_move="hard cut if stems clash",
    )
    json_str = recipe.to_json()
    restored = TransitionRecipe.from_json(json_str)
    assert restored is not None
    assert restored.fx_type == NeuralMixCrossfaderFX.NEURAL_MIX_DRUM_SWAP
    assert restored.bars == 16
    assert len(restored.steps) == 1
    assert restored.steps[0].stem_action == StemAction.FADE_IN
    assert restored.confidence == 0.85


def test_transition_recipe_from_json_legacy_fx_type():
    """Legacy fx_type values (old TransitionType strings) are silently ignored."""
    raw = json.dumps({"fx_type": "BASS_SWAP_SHORT", "bars": 8, "steps": []})
    recipe = TransitionRecipe.from_json(raw)
    assert recipe is not None
    assert recipe.fx_type is None


def test_transition_recipe_from_json_none():
    assert TransitionRecipe.from_json(None) is None


def test_transition_recipe_from_json_invalid():
    assert TransitionRecipe.from_json("not-json") is None


def test_all_neural_mix_fx_steps():
    """Every NeuralMixCrossfaderFX must produce a non-empty step sequence."""
    from app.transition.recipe_steps import build_steps_for_fx

    for fx in NeuralMixCrossfaderFX:
        steps, eq = build_steps_for_fx(fx, 16)
        assert len(steps) > 0, f"{fx} produced no steps"
        assert isinstance(eq, EQPlan)
