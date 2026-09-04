from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def test_transition_plan_is_immutable_and_canonical() -> None:
    recipe = RecipePlanner().plan(RecipeKind.EQ_BLEND, 16)
    plan = TransitionPlan.create(
        "a", "b", 16, 128.0, recipe,
        config_identity="config", source_analysis_identity="sa",
        target_analysis_identity="ta", diagnostics=("safe",),
    )
    assert plan.canonical_json() == plan.canonical_json()
    assert len(plan.execution_identity) == 64
    assert plan.config_identity == "config"
    assert plan.source_analysis_identity == "sa"
    try:
        plan.source_id = "x"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("plan must be immutable")
