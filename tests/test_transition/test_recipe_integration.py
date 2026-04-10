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
