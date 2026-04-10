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
        from_id=1, to_id=2,
        overall=0.82, bpm=0.9, harmonic=0.8, energy=0.8,
        spectral=0.7, groove=0.7, timbral=0.7,
        hard_reject=False, reject_reason=None, cached=False,
    )
    assert "recommended_style" in response
    assert "transition_type" in response
    assert "transition_bars" in response
    assert response["transition_type"] is not None
    assert isinstance(response["transition_bars"], int)


def test_format_pair_response_none_overall():
    from app.services.set.scoring import SetScoringService

    response = SetScoringService._format_pair_response(
        from_id=1, to_id=2,
        overall=None, bpm=None, harmonic=None, energy=None,
        spectral=None, groove=None, timbral=None,
        hard_reject=None, reject_reason=None, cached=False,
    )
    assert response["transition_type"] is None
    assert response["transition_bars"] is None
