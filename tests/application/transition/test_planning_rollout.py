"""Rollout tests for real transition planning through engine routing."""

from unittest.mock import MagicMock

import pytest

from app.application.engine.mode import EngineMode, EngineSelection
from app.application.transition.planning import PlanTransition
from app.domain.mixing.selection import SelectionPolicy


def test_shadow_planning_executes_legacy_and_new_for_the_same_request() -> None:
    legacy = MagicMock(return_value="legacy-plan")
    new = MagicMock(return_value="new-plan")
    compare = MagicMock(return_value="parity")
    use_case = PlanTransition(
        EngineSelection(EngineMode.SHADOW, "legacy"),
        legacy_planner=legacy,
        new_planner=new,
        compare=compare,
    )

    result = use_case.execute("candidates", "features", SelectionPolicy.BEST)

    legacy.assert_called_once_with("candidates", "features", SelectionPolicy.BEST)
    new.assert_called_once_with("candidates", "features", SelectionPolicy.BEST)
    compare.assert_called_once_with("legacy-plan", "new-plan")
    assert result.value == "new-plan"
    assert result.comparison == "parity"


def test_default_shadow_comparison_uses_decision_diagnostics() -> None:
    from app.application.transition.planning import _compare_plans
    from app.domain.mixing.plan import TransitionPlan
    from app.domain.mixing.recipes import RecipeKind, RecipePlanner
    from app.domain.mixing.transition import TransitionDecision

    recipe = RecipePlanner().plan(RecipeKind.EQ_BLEND, 8)
    legacy_plan = TransitionPlan.create("a", "b", 8, 128, recipe)
    new_plan = TransitionPlan.create("a", "b", 8, 128, recipe)
    legacy = TransitionDecision(
        legacy_plan,
        (),
        (("x", "tempo_drift"),),
        SelectionPolicy.BEST,
        score=0.70,
        technical_margin=0.20,
        dimension_scores=(("harmony", 0.80), ("energy", 0.60)),
    )
    new = TransitionDecision(
        new_plan,
        (),
        (("x", "tempo_drift"),),
        SelectionPolicy.BEST,
        score=0.75,
        technical_margin=0.25,
        dimension_scores=(("harmony", 0.90), ("energy", 0.60)),
    )

    comparison = _compare_plans(legacy, new)

    assert comparison.score_delta == 0.05
    assert comparison.technical_margin_delta == 0.05
    assert comparison.recipe_parity is True
    assert comparison.rejection_parity is True
    assert comparison.dimension_deltas == (("energy", 0.0), ("harmony", 0.1))


def test_legacy_planning_does_not_require_new_engine() -> None:
    legacy = MagicMock(return_value="legacy-plan")
    use_case = PlanTransition(
        EngineSelection(EngineMode.LEGACY, "legacy"),
        legacy_planner=legacy,
    )

    result = use_case.execute((), (), SelectionPolicy.BEST)

    assert result.value == "legacy-plan"
    assert result.comparison is None


@pytest.mark.asyncio
async def test_async_shadow_without_store_keeps_planning_result() -> None:
    legacy = MagicMock(return_value="legacy-plan")
    new = MagicMock(return_value="new-plan")
    compare = MagicMock(return_value="parity")
    use_case = PlanTransition(
        EngineSelection(EngineMode.SHADOW, "legacy"),
        legacy_planner=legacy,
        new_planner=new,
        compare=compare,
    )

    result = await use_case.execute_async("candidates", "features", SelectionPolicy.BEST)

    assert result.value == "new-plan"
    assert result.comparison == "parity"
