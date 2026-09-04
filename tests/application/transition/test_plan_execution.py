import pytest

from app.application.transition.execution import PlanDrivenRenderer
from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner


def _plan() -> TransitionPlan:
    recipe = RecipePlanner().plan(RecipeKind.EQ_BLEND, 8)
    return TransitionPlan.create("source", "target", 8, 128.0, recipe)


def test_renderer_executes_the_supplied_plan_without_replanning() -> None:
    seen: list[str] = []
    renderer = PlanDrivenRenderer(lambda plan: seen.append(plan.execution_identity))

    result = renderer.render(_plan())

    assert result == seen[0]


def test_renderer_rejects_invalid_plan_before_execution() -> None:
    calls: list[str] = []
    renderer = PlanDrivenRenderer(lambda plan: calls.append(plan.execution_identity))
    invalid = TransitionPlan.create(
        "same", "same", 8, 128.0, RecipePlanner().plan(RecipeKind.EQ_BLEND, 8)
    )

    with pytest.raises(ValueError, match="invalid transition plan"):
        renderer.render(invalid)
    assert calls == []
