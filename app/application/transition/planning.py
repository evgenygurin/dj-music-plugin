"""Feature-flagged application entry point for transition planning."""

from __future__ import annotations

from typing import Any, Protocol

from app.application.engine.mode import EngineSelection
from app.application.engine.router import EngineRunResult, TransitionEngineRouter
from app.application.transition.shadow import ShadowComparison, ShadowComparisonRecord


class TransitionPlannerPort(Protocol):
    def __call__(self, candidates: Any, features: Any, policy: Any) -> Any: ...


def _compare_plans(legacy: Any, new: Any) -> ShadowComparison:
    """Compare decision contracts with explicit score and technical diagnostics."""
    legacy_plan = getattr(legacy, "selected", getattr(legacy, "plan", legacy))
    new_plan = getattr(new, "selected", getattr(new, "plan", new))
    legacy_recipe = getattr(getattr(legacy_plan, "recipe", None), "kind", None)
    new_recipe = getattr(getattr(new_plan, "recipe", None), "kind", None)
    return ShadowComparison.compare(
        str(getattr(legacy_plan, "execution_identity", legacy_plan)),
        str(getattr(new_plan, "execution_identity", new_plan)),
        float(getattr(legacy, "score", 0.0)),
        float(getattr(new, "score", 0.0)),
        legacy_recipe=str(legacy_recipe) if legacy_recipe is not None else None,
        new_recipe=str(new_recipe) if new_recipe is not None else None,
        legacy_rejected=tuple(reason for _, reason in getattr(legacy, "rejected", ())),
        new_rejected=tuple(reason for _, reason in getattr(new, "rejected", ())),
        legacy_technical_margin=float(getattr(legacy, "technical_margin", 0.0)),
        new_technical_margin=float(getattr(new, "technical_margin", 0.0)),
        legacy_dimensions=dict(getattr(legacy, "dimension_scores", ())),
        new_dimensions=dict(getattr(new, "dimension_scores", ())),
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
        shadow_store: Any = None,
    ) -> None:
        self._selection = selection
        self._legacy = legacy_planner
        self._new = new_planner
        self._compare = compare
        self._shadow_store = shadow_store

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

    async def execute_async(
        self, candidates: Any, features: Any, policy: Any
    ) -> EngineRunResult[Any, Any]:
        """Execute planning and persist shadow diagnostics when configured."""
        result = self.execute(candidates, features, policy)
        if (
            self._selection.engine.value == "shadow"
            and result.comparison is not None
            and self._shadow_store is not None
        ):
            selected = getattr(
                result.value, "selected", getattr(result.value, "plan", result.value)
            )
            execution_identity = str(selected.execution_identity)
            await _persist_shadow_comparison(
                self._shadow_store, result.comparison, execution_identity
            )
        return result


# Async persistence is deliberately separate so existing synchronous callers remain compatible.
async def _persist_shadow_comparison(
    store: Any, comparison: ShadowComparison, execution_identity: str
) -> None:
    record = ShadowComparisonRecord.create(execution_identity, comparison)
    await store.save_shadow_comparison(
        record.identity, execution_identity, record.canonical_payload()
    )
