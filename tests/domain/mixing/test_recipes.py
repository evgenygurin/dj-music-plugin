from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def test_all_universal_recipe_kinds_are_available() -> None:
    assert len(RecipeKind) >= 15
    recipe = RecipePlanner().plan(RecipeKind.EQ_BLEND, bars=16)
    assert recipe.kind is RecipeKind.EQ_BLEND
    assert recipe.bars == 16


def test_recipe_planning_is_deterministic() -> None:
    planner = RecipePlanner()
    assert planner.plan(RecipeKind.HARD_CUT, 8) == planner.plan(RecipeKind.HARD_CUT, 8)
