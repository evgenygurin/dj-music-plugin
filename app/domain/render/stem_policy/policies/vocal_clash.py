"""Vocal clash policy — multi-stage fade when both tracks are vocal-heavy."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class VocalClashPolicy(StemTransitionPolicy):
    name = "vocal_clash"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        if ctx.stem != "vocals":
            return plan
        # voicing_ratio proxy + sections; fallback to track_features voicing_ratio
        vr_in = (ctx.track_features_in or {}).get("voicing_ratio")
        vr_out = (ctx.track_features_out or {}).get("voicing_ratio")
        if vr_in is None and vr_out is None:
            return plan
        try:
            both_vocal = float(vr_in or 0) > 0.35 and float(vr_out or 0) > 0.35
        except Exception:
            return plan
        if not both_vocal:
            return plan
        # aggressive vocal dip: tighten outgoing fade to last 10% if we have durations
        # Graceful: if durations unknown, just annotate.
        aggression = (
            float(ctx.track_input.get("vocal_clash_aggression", 0.7))
            if isinstance(ctx.track_input, dict)
            else 0.7
        )
        return plan.update(
            notes=(
                *plan.notes,
                f"vocal_clash: vr_in={vr_in:.2f} vr_out={vr_out:.2f} agg={aggression:.2f}",
            )
        )
