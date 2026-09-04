"""Feature-flagged application entry point for transition planning."""

from __future__ import annotations

from typing import Any, Protocol

from app.application.engine.mode import EngineSelection
from app.application.engine.router import EngineRunResult, TransitionEngineRouter
from app.application.transition.shadow import ShadowComparison


class TransitionPlannerPort(Protocol):
    def __call__(self, candidates: Any, features: Any, policy: Any) -> Any: ...


def _compare_plans(legacy: Any, new: Any) -> ShadowComparison:
    """Compare accepted plan contracts without coupling the router to planners."""
    legacy_plan = getattr(legacy, "plan", legacy)
    new_plan = getattr(new, "plan", new)
    legacy_recipe = getattr(getattr(legacy_plan, "recipe", None), "kind", None)
    new_recipe = getattr(getattr(new_plan, "recipe", None), "kind", None)
    return ShadowComparison.compare(
        str(getattr(legacy_plan, "execution_identity", legacy_plan)),
        str(getattr(new_plan, "execution_identity", new_plan)),
        0.0,
        0.0,
        legacy_recipe=str(legacy_recipe) if legacy_recipe is not None else None,
        new_recipe=str(new_recipe) if new_recipe is not None else None,
    )


class PlanTransition:
    """Route one planning request through legacy, shadow, or new engine."""

    def __init__(
        self,
        selection: EngineSelection,
        *,
        legacy_planner: TransitionPlannerPort,
        new_planner: TransitionPlannerPort | None = None,
        compare: Any = _compare_plans,
    ) -> None:
        self._selection = selection
        self._legacy = legacy_planner
        self._new = new_planner
        self._compare = compare

    def execute(self, candidates: Any, features: Any, policy: Any) -> EngineRunResult[Any, Any]:
        new_planner = self._new
        new_call = (
            (lambda: new_planner(candidates, features, policy))
            if new_planner is not None
            else None
        )
        return TransitionEngineRouter(
            self._selection,
            legacy=lambda: self._legacy(candidates, features, policy),
            new=new_call,
            compare=self._compare,
        ).run()
