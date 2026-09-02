"""Vocals cover policy — softer vocal fade when complexity is high."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class VocalsCoverPolicy(StemTransitionPolicy):
    name = "vocals_cover"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        if ctx.stem != "vocals":
            return plan
        dc = (ctx.track_features_in or {}).get("dynamic_complexity")
        sc = (ctx.track_features_in or {}).get("spectral_complexity_mean")
        if dc is None and sc is None:
            dc = (ctx.track_features_out or {}).get("dynamic_complexity")
            sc = (ctx.track_features_out or {}).get("spectral_complexity_mean")
        if dc is None and sc is None:
            return plan
        try:
            high = (dc is not None and float(dc) > 0.6) or (sc is not None and float(sc) > 0.6)
        except Exception:
            return plan
        if not high:
            return plan
        # soften fade curve for complex vocals
        return plan.update(
            fade_in_curve="tri",
            fade_out_curve="tri",
            notes=(*plan.notes, "vocals_cover: complex → tri"),
        )
