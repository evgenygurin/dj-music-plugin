from __future__ import annotations

import json

from dj_music.transition.recipe import (
    DjayTransition,
    EQPlan,
    RecipeStep,
    StemAction,
    TransitionRecipe,
    TransitionType,
)


def test_transition_type_has_12_values():
    assert len(TransitionType) == 12
    assert TransitionType.CUT == "cut"
    assert TransitionType.NEURAL_MIX_BLEND == "neural_mix_blend"
    assert TransitionType.STEMS_CREATIVE == "stems_creative"


def test_djay_transition_has_6_values():
    assert len(DjayTransition) == 6
    assert DjayTransition.NEURAL_MIX == "neural_mix"


def test_stem_action_values():
    assert StemAction.SWAP == "swap"
    assert StemAction.FADE_IN == "fade_in"


def test_recipe_step_creation():
    step = RecipeStep(
        bar=8,
        deck="both",
        action="BASS SWAP on the one",
        stem="bass",
        stem_action=StemAction.SWAP,
    )
    assert step.bar == 8
    assert step.stem == "bass"
    assert step.eq_band is None


def test_transition_recipe_creation():
    recipe = TransitionRecipe(
        transition_type=TransitionType.BASS_SWAP_SHORT,
        bars=8,
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(
            RecipeStep(bar=0, deck="B", action="Start B, bass killed"),
            RecipeStep(bar=8, deck="both", action="BASS SWAP"),
        ),
        eq_plan=EQPlan(low="swap@bar8", mid="gradual", high="keep"),
        mix_in_section="intro",
        mix_out_section="outro",
        phrase_align=True,
        warnings=("BPM +2",),
        confidence=0.88,
        subgenre_modifier=None,
        rescue_move="filter sweep + hard cut",
    )
    assert recipe.bars == 8
    assert len(recipe.steps) == 2
    assert recipe.steps[0].deck == "B"


def test_recipe_to_dict():
    recipe = TransitionRecipe(
        transition_type=TransitionType.CUT,
        bars=0,
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(),
        eq_plan=EQPlan(low="keep", mid="keep", high="keep"),
        mix_in_section=None,
        mix_out_section=None,
        phrase_align=True,
        warnings=(),
        confidence=0.95,
        subgenre_modifier=None,
        rescue_move="hard cut",
    )
    d = recipe.to_dict()
    assert d["transition_type"] == "cut"
    assert d["bars"] == 0
    json.dumps(d)  # Must be JSON-serializable


def test_recipe_from_json_round_trip():
    recipe = TransitionRecipe(
        transition_type=TransitionType.BASS_SWAP_SHORT,
        bars=8,
        djay_transition=DjayTransition.NEURAL_MIX,
        djay_tempo_adjust="gradual",
        steps=(
            RecipeStep(
                bar=4,
                deck="both",
                action="Swap bass",
                stem="bass",
                stem_action=StemAction.SWAP,
                eq_band="low",
                eq_value=0.0,
                effect="echo",
                effect_param=0.5,
            ),
        ),
        eq_plan=EQPlan(low="swap", mid="gradual", high="keep"),
        mix_in_section="intro",
        mix_out_section="outro",
        phrase_align=True,
        warnings=("watch vocals",),
        confidence=0.83,
        subgenre_modifier="hard_pair",
        rescue_move="hard cut",
    )

    assert TransitionRecipe.from_json(recipe.to_json()) == recipe


def test_recipe_from_json_returns_none_for_wrong_shaped_payload():
    assert TransitionRecipe.from_json("[]") is None


def test_recipe_from_json_returns_none_for_malformed_nested_payload():
    payload = json.dumps(
        {
            "transition_type": "cut",
            "bars": 4,
            "djay_transition": "none",
            "steps": [[]],
            "eq_plan": {"low": "keep", "mid": "keep", "high": "keep"},
            "confidence": 0.8,
            "rescue_move": "hard cut",
        }
    )

    assert TransitionRecipe.from_json(payload) is None
