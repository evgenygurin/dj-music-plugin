"""Pre-render validation of immutable transition plans."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.mixing.plan import TransitionPlan


@dataclass(frozen=True, slots=True)
class PlanValidation:
    accepted: bool
    reason: str | None = None


class RenderPlanValidator:
    def validate(self, plan: TransitionPlan) -> PlanValidation:
        if plan.duration_bars <= 0:
            return PlanValidation(False, "duration_bars")
        if plan.recipe.bars != plan.duration_bars:
            return PlanValidation(False, "recipe_duration")
        if plan.effective_bpm <= 0:
            return PlanValidation(False, "effective_bpm")
        return PlanValidation(True)
