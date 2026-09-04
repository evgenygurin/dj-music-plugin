from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.render.plan_validator import RenderPlanValidator


def test_render_plan_validator_rejects_zero_duration() -> None:
    plan = TransitionPlan.create("a", "b", 0, 128, RecipePlanner().plan(RecipeKind.FADE, 0))
    result = RenderPlanValidator().validate(plan)
    assert not result.accepted
    assert result.reason == "duration_bars"


def test_render_plan_validator_accepts_valid_plan() -> None:
    plan = TransitionPlan.create("a", "b", 8, 128, RecipePlanner().plan(RecipeKind.FADE, 8))
    assert RenderPlanValidator().validate(plan).accepted
