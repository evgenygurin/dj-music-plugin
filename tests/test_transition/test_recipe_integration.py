import json

from dj_music.schemas.audio import TrackFeatures
from dj_music.transition import TransitionRecipe, TransitionType, recommend_recipe
from dj_music.transition.recipe import DjayTransition, EQPlan
from dj_music.transition.score import TransitionScore


def test_recommend_recipe_with_features():
    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.7, timbral=0.7, overall=0.82
    )
    fa = TrackFeatures(bpm=130.0, key_code=15, integrated_lufs=-8.0)
    fb = TrackFeatures(bpm=132.0, key_code=16, integrated_lufs=-7.5)
    recipe = recommend_recipe(score, fa, fb)
    assert isinstance(recipe, TransitionRecipe)
    assert recipe.bars >= 0


def test_recommend_recipe_fallback_without_features():
    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.7, timbral=0.7, overall=0.82
    )
    recipe = recommend_recipe(score)
    assert isinstance(recipe, TransitionRecipe)
    assert recipe.transition_type in TransitionType
    assert recipe.confidence == 0.5  # fallback confidence


def test_format_pair_response_includes_recipe():
    from dj_music.services.set.scoring import SetScoringService

    response = SetScoringService._format_pair_response(
        from_id=1,
        to_id=2,
        overall=0.82,
        bpm=0.9,
        harmonic=0.8,
        energy=0.8,
        spectral=0.7,
        groove=0.7,
        timbral=0.7,
        hard_reject=False,
        reject_reason=None,
        cached=False,
    )
    assert "recommended_style" in response
    assert "transition_type" in response
    assert "transition_bars" in response
    assert response["transition_type"] is not None
    assert isinstance(response["transition_bars"], int)


def test_format_pair_response_none_overall():
    from dj_music.services.set.scoring import SetScoringService

    response = SetScoringService._format_pair_response(
        from_id=1,
        to_id=2,
        overall=None,
        bpm=None,
        harmonic=None,
        energy=None,
        spectral=None,
        groove=None,
        timbral=None,
        hard_reject=None,
        reject_reason=None,
        cached=False,
    )
    assert response["transition_type"] is None
    assert response["transition_bars"] is None


def test_format_pair_response_uses_persisted_recipe_json():
    from dj_music.services.set.scoring import SetScoringService

    persisted = TransitionRecipe(
        transition_type=TransitionType.CUT,
        bars=4,
        djay_transition=DjayTransition.FILTER,
        djay_tempo_adjust="sync",
        steps=(),
        eq_plan=EQPlan(low="keep", mid="keep", high="keep"),
        mix_in_section=None,
        mix_out_section=None,
        phrase_align=True,
        warnings=(),
        confidence=0.91,
        subgenre_modifier=None,
        rescue_move="hard cut",
    )

    response = SetScoringService._format_pair_response(
        from_id=1,
        to_id=2,
        overall=0.82,
        bpm=0.9,
        harmonic=0.8,
        energy=0.8,
        spectral=0.7,
        groove=0.7,
        timbral=0.7,
        hard_reject=False,
        reject_reason=None,
        cached=True,
        persisted_recipe_json=persisted.to_json(),
    )

    assert response["transition_type"] == "cut"
    assert response["transition_bars"] == 4
    assert response["djay_transition"] == "filter"
    assert response["recipe_confidence"] == 0.91


def test_format_pair_response_falls_back_for_wrong_shaped_persisted_recipe_json():
    from dj_music.services.set.scoring import SetScoringService

    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.7, timbral=0.7, overall=0.82
    )
    expected = recommend_recipe(score)

    response = SetScoringService._format_pair_response(
        from_id=1,
        to_id=2,
        overall=score.overall,
        bpm=score.bpm,
        harmonic=score.harmonic,
        energy=score.energy,
        spectral=score.spectral,
        groove=score.groove,
        timbral=score.timbral,
        hard_reject=score.hard_reject,
        reject_reason=score.reject_reason,
        cached=True,
        persisted_recipe_json="[]",
    )

    assert response["transition_type"] == expected.transition_type.value
    assert response["transition_bars"] == expected.bars
    assert response["djay_transition"] == expected.djay_transition.value
    assert response["recipe_confidence"] == expected.confidence


def test_format_pair_response_falls_back_for_malformed_nested_recipe_json():
    from dj_music.services.set.scoring import SetScoringService

    score = TransitionScore(
        bpm=0.9, harmonic=0.8, energy=0.8, spectral=0.7, groove=0.7, timbral=0.7, overall=0.82
    )
    expected = recommend_recipe(score)
    malformed = json.dumps(
        {
            "transition_type": "cut",
            "bars": 4,
            "djay_transition": "none",
            "steps": [{"bar": 0, "deck": "B", "action": "ok"}],
            "eq_plan": [],
            "confidence": 0.99,
            "rescue_move": "hard cut",
        }
    )

    response = SetScoringService._format_pair_response(
        from_id=1,
        to_id=2,
        overall=score.overall,
        bpm=score.bpm,
        harmonic=score.harmonic,
        energy=score.energy,
        spectral=score.spectral,
        groove=score.groove,
        timbral=score.timbral,
        hard_reject=score.hard_reject,
        reject_reason=score.reject_reason,
        cached=True,
        persisted_recipe_json=malformed,
    )

    assert response["transition_type"] == expected.transition_type.value
    assert response["transition_bars"] == expected.bars
    assert response["djay_transition"] == expected.djay_transition.value
    assert response["recipe_confidence"] == expected.confidence


def test_format_recipe_box():
    from dj_music.services.set.cheatsheet import _format_recipe_box
    from dj_music.transition.recipe import (
        DjayTransition,
        EQPlan,
        RecipeStep,
        TransitionRecipe,
        TransitionType,
    )

    recipe = TransitionRecipe(
        transition_type=TransitionType.BASS_SWAP_SHORT,
        bars=16,
        djay_transition=DjayTransition.NONE,
        djay_tempo_adjust="sync",
        steps=(
            RecipeStep(bar=0, deck="B", action="Start B, bass killed"),
            RecipeStep(bar=8, deck="both", action="BASS SWAP on the one"),
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
    text = _format_recipe_box(recipe, score=0.85)
    assert "BASS SWAP SHORT" in text
    assert "16 bars" in text
    assert "bar 0" in text
    assert "bar 8" in text
    assert "BASS SWAP on the one" in text
    assert "swap@bar8" in text
    assert "Rescue" in text
    assert "0.85" in text


def test_export_transition_has_recipe_fields():
    from dj_music.export.models import ExportTransition

    et = ExportTransition(
        from_position=0,
        to_position=1,
        score=0.82,
        transition_type="bass_swap_short",
        transition_bars=16,
        djay_transition="none",
        recipe_steps=[{"bar": 0, "deck": "B", "action": "test"}],
        eq_plan={"low": "swap", "mid": "keep", "high": "keep"},
        rescue_move="hard cut",
    )
    assert et.transition_bars == 16
    assert et.recipe_steps is not None
    assert len(et.recipe_steps) == 1
