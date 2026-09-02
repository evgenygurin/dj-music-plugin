"""Scoring profile policy — scale gain_db by per-stem weights."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class ScoringProfilePolicy(StemTransitionPolicy):
    name = "scoring_profile"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        weights = (
            (ctx.track_input.get("scoring_profile_weights") or {})
            if isinstance(ctx.track_input, dict)
            else {}
        )
        w = weights.get(ctx.stem)
        if w is None:
            return plan
        try:
            wf = float(w)
        except Exception:
            return plan
        # weight 1.0 → 0 dB, 0.5 → -1 dB, 1.5 → +1 dB (gentle)
        gain_adj = (wf - 1.0) * 2.0
        gain_adj = max(-3.0, min(3.0, gain_adj))
        if abs(gain_adj) < 0.05:
            return plan
        return plan.update(
            gain_db=plan.gain_db + gain_adj,
            notes=(*plan.notes, f"scoring_profile: {ctx.stem} w={wf:.2f}"),
        )
