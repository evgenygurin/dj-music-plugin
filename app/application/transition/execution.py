"""Plan-driven transition rendering boundary.

The application layer owns validation and execution identity; concrete DSP
renderers receive the immutable plan and must not select or re-plan it.
"""

from __future__ import annotations

from collections.abc import Callable

from app.domain.mixing.plan import TransitionPlan
from app.domain.render.plan_validator import RenderPlanValidator


class PlanDrivenRenderer:
    def __init__(self, executor: Callable[[TransitionPlan], None]) -> None:
        self._executor = executor
        self._validator = RenderPlanValidator()

    def render(self, plan: TransitionPlan) -> str:
        validation = self._validator.validate(plan)
        if not validation.accepted:
            raise ValueError(f"invalid transition plan: {validation.reason}")
        self._executor(plan)
        return plan.execution_identity
