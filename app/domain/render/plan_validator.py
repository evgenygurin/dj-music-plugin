"""Pre-render validation of immutable transition plans."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.mixing.plan import TransitionPlan


@dataclass(frozen=True, slots=True)
class PlanValidation:
    accepted: bool
    reasons: tuple[str, ...] = ()

    @property
    def reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None


class RenderPlanValidator:
    def validate(self, plan: TransitionPlan) -> PlanValidation:
        reasons: list[str] = []
        if plan.duration_bars <= 0:
            reasons.append("duration_bars")
        if plan.recipe.bars != plan.duration_bars:
            reasons.append("recipe_duration")
        if plan.effective_bpm <= 0:
            reasons.append("effective_bpm")
        if plan.source_id == plan.target_id:
            reasons.append("self_transition")
        return PlanValidation(not reasons, tuple(reasons))
