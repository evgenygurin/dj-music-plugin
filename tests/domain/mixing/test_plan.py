from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def test_transition_plan_is_immutable_and_canonical() -> None:
    recipe = RecipePlanner().plan(RecipeKind.EQ_BLEND, 16)
    plan = TransitionPlan.create("a", "b", 16, 128.0, recipe)
    assert plan.canonical_json() == plan.canonical_json()
    assert len(plan.execution_identity) == 64
    try:
        plan.source_id = "x"  # type: ignore[misc]
    except AttributeError:
        pass
    else:
        raise AssertionError("plan must be immutable")
