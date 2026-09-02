"""User history policy — lengthen blend when affinity is negative."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class UserHistoryPolicy(StemTransitionPolicy):
    name = "user_history"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        available = ctx.available
        if available is None or not available.has_affinity:
            return plan
        affinity = (
            (ctx.track_input.get("affinity") or {}) if isinstance(ctx.track_input, dict) else {}
        )
        sentiment = affinity.get("net_sentiment")
        if sentiment is None:
            return plan
        try:
            if float(sentiment) >= 0:
                return plan
        except Exception:
            return plan
        # lengthen fades modestly when history is negative
        new_in = plan.fade_in_s * 1.25 if plan.fade_in_s is not None else None
        new_out = plan.fade_out_s * 1.25 if plan.fade_out_s is not None else None
        return plan.update(
            fade_in_s=new_in,
            fade_out_s=new_out,
            notes=(*plan.notes, f"user_history: sentiment={sentiment:.2f}"),
        )
