"""Beat strength policy — sharper bass pinpoint when kick is prominent."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class BeatStrengthPolicy(StemTransitionPolicy):
    name = "beat_strength"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        if ctx.stem != "bass":
            return plan
        kp = (ctx.track_features_out or {}).get("kick_prominence")
        if kp is None:
            kp = (ctx.track_features_in or {}).get("kick_prominence")
        if kp is None:
            return plan
        try:
            if float(kp) <= 0.70:
                return plan
        except Exception:
            return plan
        if plan.pinpoint_s is None:
            return plan.update(notes=(*plan.notes, f"beat_strength: kick_prom={kp:.2f}"))
        tightened = max(0.05, plan.pinpoint_s * 0.80)
        return plan.update(
            pinpoint_s=tightened, notes=(*plan.notes, f"beat_strength: kick_prom={kp:.2f}")
        )
