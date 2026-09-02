"""BPM discrepancy policy — lengthen bass pinpoint when tempo delta >1 BPM."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class BpmDiscrepancyPolicy(StemTransitionPolicy):
    name = "bpm_discrepancy"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        bpm_in = (ctx.track_features_in or {}).get("bpm")
        bpm_out = (ctx.track_features_out or {}).get("bpm")
        if bpm_in is None or bpm_out is None:
            return plan
        try:
            delta = abs(float(bpm_in) - float(bpm_out))
        except Exception:
            return plan
        if delta <= 1.0:
            return plan
        if ctx.stem != "bass" or plan.pinpoint_s is None:
            return plan.update(notes=(*plan.notes, f"bpm_discrepancy: delta={delta:.2f}"))
        stretched = min(plan.pinpoint_s * 1.35, ctx.base_d_in_s * 0.5)
        return plan.update(
            pinpoint_s=stretched, notes=(*plan.notes, f"bpm_discrepancy: delta={delta:.2f}")
        )
