from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def test_transition_plan_is_immutable_and_serializable() -> None:
    plan = TransitionPlan.create(
        "source", "target", 16, 128.0, RecipePlanner().plan(RecipeKind.EQ_BLEND, 16)
    )
    assert plan.source_id == "source"
    assert plan.canonical_json().startswith("{")
    try:
        plan.duration_bars = 8
    except AttributeError:
        pass
    else:
        raise AssertionError("TransitionPlan must be immutable")
