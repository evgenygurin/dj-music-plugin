"""Transition recipe policy — reuse historical recipe if pair was rendered before."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class TransitionRecipePolicy(StemTransitionPolicy):
    name = "transition_recipe"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_transition_recipe:
            return plan
        recipe = (
            (ctx.track_input.get("transition_recipe") or {})
            if isinstance(ctx.track_input, dict)
            else {}
        )
        if not recipe:
            return plan
        # recipe is per-stem key-frames; if it mentions this stem, annotate
        if ctx.stem in recipe or "all" in recipe:
            return plan.update(notes=(*plan.notes, f"transition_recipe: reuse {ctx.stem}"))
        return plan
