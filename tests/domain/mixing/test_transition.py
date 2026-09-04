from app.domain.mixing.plan import TransitionPlan
from app.domain.mixing.recipes import RecipeKind, RecipePlanner
from app.domain.mixing.selection import SelectionPolicy
from app.domain.mixing.transition import TransitionDecision


def test_decision_retains_selected_alternatives_and_rejections() -> None:
    plan = TransitionPlan.create("a", "b", 8, 128.0, RecipePlanner().plan(RecipeKind.FADE, 8))
    decision = TransitionDecision(
        selected=plan,
        alternatives=("c",),
        rejected=(("d", "tempo_drift"),),
        policy=SelectionPolicy.BEST,
    )
    assert decision.rejected[0][1] == "tempo_drift"
