"""Rollout tests for real transition planning through engine routing."""

from unittest.mock import MagicMock

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


def test_legacy_planning_does_not_require_new_engine() -> None:
    legacy = MagicMock(return_value="legacy-plan")
    use_case = PlanTransition(
        EngineSelection(EngineMode.LEGACY, "legacy"),
        legacy_planner=legacy,
    )

    result = use_case.execute((), (), SelectionPolicy.BEST)

    assert result.value == "legacy-plan"
    assert result.comparison is None
