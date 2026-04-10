from app.entities.audio.features import TrackFeatures
from app.transition import TransitionRecipe, TransitionType, recommend_recipe
from app.transition.score import TransitionScore


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
    from app.services.set.scoring import SetScoringService

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
    from app.services.set.scoring import SetScoringService

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


def test_format_recipe_box():
    from app.services.set.cheatsheet import _format_recipe_box
    from app.transition.recipe import (
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
    from app.export.models import ExportTransition

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
