"""Spectral clash policy — tighten bass pinpoint when sub energies collide."""

from __future__ import annotations

from app.domain.render.stem_policy.models import (
    FadePlan,
    StemTransitionContext,
    StemTransitionPolicy,
)


class SpectralClashPolicy(StemTransitionPolicy):
    name = "spectral_clash"

    def merge(self, plan: FadePlan, ctx: StemTransitionContext) -> FadePlan:
        if ctx.stem != "bass":
            return plan
        r_in = (ctx.track_features_in or {}).get("energy_sub_ratio")
        r_out = (ctx.track_features_out or {}).get("energy_sub_ratio")
        if r_in is None or r_out is None:
            return plan
        try:
            s = float(r_in) + float(r_out)
        except Exception:
            return plan
        if s <= 0.30:
            return plan
        # tighten pinpoint window a bit (faster swap) when both are sub-heavy
        if plan.pinpoint_s is None:
            return plan.update(
                notes=(*plan.notes, f"spectral_clash: sub_sum={s:.2f} (no pinpoint)")
            )
        tightened = max(0.05, plan.pinpoint_s * 0.85)
        return plan.update(
            pinpoint_s=tightened, notes=(*plan.notes, f"spectral_clash: sub_sum={s:.2f}")
        )
