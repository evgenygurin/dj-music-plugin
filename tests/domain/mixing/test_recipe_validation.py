from app.domain.mixing.recipe_validation import RecipeValidator
from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def test_recipe_validator_rejects_invalid_duration() -> None:
    recipe = RecipePlanner().plan(RecipeKind.FADE, bars=0)
    result = RecipeValidator().validate(recipe)
    assert not result.accepted
    assert result.reason == "bars_positive"


def test_recipe_validator_accepts_supported_recipe() -> None:
    recipe = RecipePlanner().plan(RecipeKind.DROP_TO_DROP, bars=16)
    assert RecipeValidator().validate(recipe).accepted
